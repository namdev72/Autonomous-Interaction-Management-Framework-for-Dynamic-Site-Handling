from typing import List, Dict, Any, Optional
import json
import os
import chromadb
from models.action_models import AgentAction
from loguru import logger

class MemoryState:
    def __init__(self, persist_dir: str = "./memory_db"):
        self.actions_history: List[AgentAction] = []
        self.visited_urls: List[str] = []
        self.extracted_data: Dict[str, Any] = {}
        self.persist_dir = persist_dir
        
        # Initialize ChromaDB for vector search
        os.makedirs(self.persist_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.chroma_client.get_or_create_collection(name="agent_history")
    def add_action(self, action: AgentAction):
        self.actions_history.append(action)
        
    def add_url(self, url: str):
        if not self.visited_urls or self.visited_urls[-1] != url:
            self.visited_urls.append(url)
            
    def store_extracted_data(self, key: str, value: Any):
        self.extracted_data[key] = value
        logger.info(f"Stored in memory: {key} = {value}")
        
    def save_state(self):
        state = {
            "actions": [a.model_dump() for a in self.actions_history],
            "visited_urls": self.visited_urls,
            "extracted_data": self.extracted_data
        }
        with open(os.path.join(self.persist_dir, "state.json"), "w") as f:
            json.dump(state, f, indent=4)

    def index_page_content(self, url: str, content: str):
        # Index page contents in vector DB
        doc_id = f"page_{len(self.visited_urls)}"
        self.collection.upsert(
            documents=[content],
            metadatas=[{"url": url}],
            ids=[doc_id]
        )

    def semantic_search(self, query: str, n_results: int = 1) -> List[str]:
        if self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, self.collection.count())
        )
        return results["documents"][0] if results["documents"] else []
        
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
        if self.extracted_data:
            context += f"\n\nExtracted Data So Far:\n{self.extracted_data}"
        return context
