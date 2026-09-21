import asyncio
import datetime
import sys
import time
import uuid
from typing import Dict, Optional, Any

if sys.platform == 'win32':
    # Playwright launches a subprocess and requires Proactor on Windows.
    # The entrypoint below disables reload because Uvicorn reload can conflict
    # with Proactor socket registration on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# Import the existing agent architecture
from agents.reasoning_agent import ReasoningAgent
from agents.answer_composer import compose_comparison_answer
from agents.task_planner import TaskPlanner
from models.task_models import TaskPlan
from sites.adapters import compare_sites
from sites.registry import allowed_hosts, policy_for

# Configure loguru for FastAPI
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

app = FastAPI(title="PRISM Agent UI Backend")

# Allow CORS for React frontend (default dev server port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, we allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentSession:
    def __init__(self, query: str):
        self.id = uuid.uuid4().hex
        self.queue = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
        self.last_active = time.monotonic()
        self.query = query
        self.plan: Optional[TaskPlan] = None
        self.waiting_for_user = False
        
    async def enqueue_event(self, event_type: str, data: dict):
        # We wrap the underlying agent events into a unified structure
        await self.queue.put({
            "type": event_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "data": data
        })

# Store active sessions
sessions: Dict[str, AgentSession] = {}

# A session is removed once its run has ended and the UI has read every event.
# Sessions abandoned before that (the UI never connected, a question was never
# answered) are removed after this long, so a long-running server does not
# keep every request in memory.
SESSION_TTL_SECONDS = 30 * 60


def prune_sessions(now: Optional[float] = None) -> int:
    """Drop idle sessions older than the TTL; running ones are kept. Returns how many."""
    now = time.monotonic() if now is None else now
    stale = [session_id for session_id, session in sessions.items()
             if not (session.task and not session.task.done())
             and now - session.last_active > SESSION_TTL_SECONDS]
    for session_id in stale:
        sessions.pop(session_id, None)
    return len(stale)

class RunRequest(BaseModel):
    query: str


class UserResponse(BaseModel):
    answer: str


from router.task_router import TaskRouter
from models.strategy_models import DirectURLStrategy, RegistryStrategy, LLMStrategy

planner = TaskPlanner()
router = TaskRouter()

async def _run_agent(session: AgentSession, query: str, plan: TaskPlan):
    async def on_event(event_type: str, data: dict):
        import datetime
        event_obj = {
            "type": event_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "data": data,
        }
        await session.queue.put(event_obj)
        if event_type == "log":
            print(f"[{event_type}] {data.get('level')} - {data.get('message')}")
        else:
            print(f"[{event_type}] {data}")

    # Everything below is inside the try so that any failure still reaches the
    # finally, which closes the WebSocket; otherwise the UI waits forever.
    try:
        await on_event("agent_started", {"message": "Agent execution starting...", "plan": plan.model_dump()})
        if plan.task_type == "compare":
            await on_event("log", {"level": "info", "message": f"Comparing approved sites: {', '.join(plan.candidate_sites)}"})
            comparison = await compare_sites(plan)
            answer = compose_comparison_answer(plan, comparison)
            # Completed only if at least one site actually ran; a crashed or
            # blocked site is not a successful comparison.
            completed = any(result.status == "completed" for result in comparison)
            if completed:
                reason = "comparison_complete"
            elif comparison and all(result.status == "blocked" for result in comparison):
                reason = "sites_blocked"
            else:
                reason = "comparison_failed"
            await on_event("agent_completed", {"result": {
                "completed": completed,
                "iterations": 1,
                "reason": reason,
                "extracted_data": answer,
                "last_url": None,
            }})
            return

        # Routing and the agent are only for the reasoning path: the agent
        # opens Chroma and SQLite connections that comparisons never use.
        start_time = time.time()
        strategy = router.route_task(query, plan)
        url_generation_latency = int((time.time() - start_time) * 1000)

        if isinstance(strategy, DirectURLStrategy):
            await on_event("strategy", {
                "strategy": "direct_url",
                "website": strategy.website,
                "url_generated": True,
                "browser_actions_saved": 4, # Approximate saved actions
                "url_generation_latency_ms": url_generation_latency
            })
        elif isinstance(strategy, RegistryStrategy):
            await on_event("strategy", {
                "strategy": "registry",
                "website": strategy.website
            })
        else:
            await on_event("strategy", {
                "strategy": "llm",
                "website": "unknown"
            })

        enforce_hosts = getattr(strategy, "source_locked", False)
        hosts = allowed_hosts() if enforce_hosts else None

        agent = ReasoningAgent(
            headless=False,
            max_iterations=20,
            allowed_hosts=hosts,
            on_event=on_event,
        )
        result = await agent.execute_task(query, strategy=strategy)
        await on_event("agent_completed", {"result": result.model_dump()})
    except asyncio.CancelledError:
        await on_event("agent_stopped", {"message": "Agent execution was cancelled by user."})
    except Exception as e:
        logger.exception("Agent execution failed")
        await on_event("error", {"message": f"{type(e).__name__}: {e}"})
    finally:
        await session.queue.put(None)

@app.post("/api/agent/run")
async def start_agent(req: RunRequest):
    prune_sessions()
    session = AgentSession(req.query)
    sessions[session.id] = session

    plan = planner.plan(req.query)
    session.plan = plan
    if plan.needs_clarification:
        session.waiting_for_user = True
        await session.queue.put({
            "type": "user_input_required",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "data": {
                "question": plan.clarification_question,
                "options": plan.clarification_options,
                "field": "site_or_region",
            },
        })
        return {"session_id": session.id, "status": "waiting_for_user"}

    session.task = asyncio.create_task(_run_agent(session, req.query, plan))
    
    return {"session_id": session.id}


@app.post("/api/agent/respond/{session_id}")
async def respond_to_agent(session_id: str, response: UserResponse):
    session = sessions.get(session_id)
    if not session or not session.waiting_for_user:
        return {"status": "not_waiting"}
    session.last_active = time.monotonic()

    clarified_query = f"{session.query}\nUser clarification: {response.answer}"
    plan = planner.plan(session.query, response.answer)
    session.plan = plan
    if plan.needs_clarification:
        await session.queue.put({
            "type": "user_input_required",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "data": {
                "question": plan.clarification_question,
                "options": plan.clarification_options,
                "field": "site_or_region",
            },
        })
        return {"status": "waiting_for_user"}

    session.waiting_for_user = False
    session.task = asyncio.create_task(_run_agent(session, clarified_query, plan))
    return {"status": "started"}

@app.post("/api/agent/stop/{session_id}")
async def stop_agent(session_id: str):
    if session_id in sessions:
        session = sessions[session_id]
        if session.task and not session.task.done():
            session.task.cancel()
            return {"status": "cancelled"}
        if session.waiting_for_user:
            # No task exists yet; end the session and close its WebSocket.
            session.waiting_for_user = False
            await session.enqueue_event("agent_stopped", {"message": "Agent execution was cancelled by user."})
            await session.queue.put(None)
            return {"status": "cancelled"}
    return {"status": "not_found"}

@app.websocket("/api/agent/ws/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.send_json({
            "type": "error",
            "timestamp": "",
            "data": {"message": "Session not found."}
        })
        await websocket.close()
        return

    session = sessions[session_id]
    finished = False

    try:
        while True:
            # Wait for events from the agent
            event = await session.queue.get()
            if event is None:
                # Sentinel reached, execution finished
                finished = True
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    finally:
        # A finished run whose events were all delivered is done with. A
        # disconnect may be a network blip, so that session is kept for the
        # UI to reconnect, and prune_sessions() removes it if it never does.
        if finished:
            sessions.pop(session_id, None)
        else:
            session.last_active = time.monotonic()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
