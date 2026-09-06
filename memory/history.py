from typing import List, Dict, Any, Optional
import json
import os
import time
import uuid
import chromadb
from pydantic import BaseModel
from memory.signature import page_key
from models.action_models import AgentAction
from models.orchestration_models import ActionResult
from loguru import logger


class StepRecord(BaseModel):
    """
    One executed action paired with the result it produced.

    An iteration can execute several actions (the decided one, a loop
    correction, a recovery action, a vision retry), so pairing has to be
    captured per execution rather than per iteration. Action and result are
    stored as snapshots taken at execution time.
    """

    step_id: str
    iteration: int
    origin: str
    action: AgentAction
    result: ActionResult


DEFAULT_MEMORY_DIR = os.path.join(".", "memory_db")

# Bounded retry for Chroma writes. Hard cap: never block the agent on a lock.
CHROMA_WRITE_ATTEMPTS = 3
CHROMA_WRITE_BACKOFF_BASE = 0.05  # seconds; doubles per retry -> 50ms, 100ms

class MemoryState:
    def __init__(self, persist_dir: str = None, run_id: str = None):
        self.actions_history: List[AgentAction] = []
        self.results_history: List[ActionResult] = []
        self.steps_history: List[StepRecord] = []
        self.visited_urls: List[str] = []
        self.extracted_data: Dict[str, Any] = {}
        # The vector store is durable and shared across runs; only per-run
        # artifacts (state.json) are namespaced under runs/<run_id>.
        self.persist_dir = persist_dir or DEFAULT_MEMORY_DIR
        self.run_id = run_id or f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        self.run_dir = os.path.join(self.persist_dir, "runs", self.run_id)
        self.chroma_client = None
        self.collection = None

        os.makedirs(self.run_dir, exist_ok=True)
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.chroma_client.get_or_create_collection(name="agent_history")
        except BaseException as e:
            logger.warning(f"ChromaDB memory unavailable; continuing with in-process memory only: {e}")

    def add_action(self, action: AgentAction):
        self.actions_history.append(action)

    def add_result(self, result: ActionResult):
        self.results_history.append(result)

    def add_step(self, record: StepRecord):
        """Record one executed action together with the result it produced."""
        self.steps_history.append(record)

    def add_url(self, url: str):
        if not self.visited_urls or self.visited_urls[-1] != url:
            self.visited_urls.append(url)
            
    def store_extracted_data(self, key: str, value: Any):
        self.extracted_data[key] = value
        logger.info(f"Stored in memory: {key} = {value}")
        
    def save_state(self):
        state = {
            "run_id": self.run_id,
            "actions": [a.model_dump() for a in self.actions_history],
            "results": [r.model_dump() for r in self.results_history],
            "steps": [s.model_dump() for s in self.steps_history],
            "visited_urls": self.visited_urls,
            "extracted_data": self.extracted_data
        }
        with open(os.path.join(self.run_dir, "state.json"), "w") as f:
            json.dump(state, f, indent=4)

    def _chroma_write(self, description: str, write) -> bool:
        """
        Run a Chroma write with a small bounded retry, then degrade loudly.

        The shared store is single-writer, so a concurrent run can hold the lock
        for a moment. Retrying briefly rides that out. Interim measure only:
        real multi-user concurrency needs server-mode Chroma or Qdrant, not this.
        """
        last_error = None
        for attempt in range(1, CHROMA_WRITE_ATTEMPTS + 1):
            try:
                write()
                return True
            except Exception as e:
                last_error = e
                if attempt < CHROMA_WRITE_ATTEMPTS:
                    delay = CHROMA_WRITE_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.debug(
                        f"Chroma {description} failed on attempt {attempt}/{CHROMA_WRITE_ATTEMPTS}; "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)

        logger.warning(
            f"Chroma {description} failed after {CHROMA_WRITE_ATTEMPTS} retries, "
            f"using in-process fallback; this write will not persist: {last_error}"
        )
        return False

    def index_page_content(self, url: str, content: str, key: str = None) -> bool:
        """
        Index one page. Keyed by page identity, so revisiting a page updates
        its document instead of adding a near-duplicate per scroll position.

        Callers that already computed the key pass it in, so a run computes it
        once; otherwise it is derived from the URL here.
        """
        if not self.collection:
            return False

        doc_id = key or page_key(url)
        metadata = {"url": url, "run_id": self.run_id, "indexed_at": int(time.time())}
        return self._chroma_write(
            f"page index for {url}",
            lambda: self.collection.upsert(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )
        )

    def semantic_search(self, query: str, n_results: int = 1) -> List[str]:
        if not self.collection:
            return []
        try:
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, count)
            )
            return results["documents"][0] if results["documents"] else []
        except Exception as e:
            logger.warning(f"Failed to query vector memory: {e}")
            return []
        
    def detect_loop(self) -> bool:
        if len(self.actions_history) < 3:
            return False
        
        last_3 = self.actions_history[-3:]
        first = last_3[0]
        for a in last_3[1:]:
            if a.action != first.action or a.target != first.target or a.value != first.value:
                return False
        return True
        
    def get_context_string(self) -> str:
        """Returns a string representation of recent history for the LLM prompt."""
        recent_actions = self.actions_history[-5:] # Last 5 actions
        history_strs = [f"- {a.action} on {a.target} (Reason: {a.reasoning})" for a in recent_actions]
        
        context = "Recent Actions Taken:\n" + ("\n".join(history_strs) if history_strs else "None")
        recent_results = self.results_history[-3:]
        if recent_results:
            result_strs = [
                f"- {r.action} success={r.success} target={r.target} error={r.error} url={r.url_after}"
                for r in recent_results
            ]
            context += "\n\nRecent Action Results:\n" + "\n".join(result_strs)
        if self.extracted_data:
            context += f"\n\nExtracted Data So Far:\n{self.extracted_data}"
        return context
