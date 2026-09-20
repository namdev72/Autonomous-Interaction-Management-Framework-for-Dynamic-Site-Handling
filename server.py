import asyncio
import sys
import uuid
from typing import Dict, Optional, Any

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# Import the existing agent architecture
from agents.reasoning_agent import ReasoningAgent

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
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.queue = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
        
    async def enqueue_event(self, event_type: str, data: dict):
        # We wrap the underlying agent events into a unified structure
        await self.queue.put({
            "type": event_type,
            "timestamp": asyncio.get_event_loop().time(), # we'll format real timestamp in frontend or here
            "data": data
        })

# Store active sessions
sessions: Dict[str, AgentSession] = {}

class RunRequest(BaseModel):
    query: str

@app.post("/api/agent/run")
async def start_agent(req: RunRequest):
    session = AgentSession()
    sessions[session.id] = session
    
    # Define the callback that bridges the ReasoningAgent events to our WebSocket queue
    async def on_event(event_type: str, data: dict):
        import datetime
        event_obj = {
            "type": event_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "data": data
        }
        await session.queue.put(event_obj)
        # Also print to terminal
        if event_type == "log":
            print(f"[{event_type}] {data.get('level')} - {data.get('message')}")
        else:
            print(f"[{event_type}] {data}")

    # Initialize the agent. headless=False ensures the browser is visible!
    agent = ReasoningAgent(
        headless=False,
        max_iterations=20,
        on_event=on_event
    )
    
    async def agent_task_runner():
        try:
            await on_event("agent_started", {"message": "Agent execution starting..."})
            result = await agent.execute_task(req.query)
            await on_event("agent_completed", {"result": result.model_dump()})
        except asyncio.CancelledError:
            await on_event("agent_stopped", {"message": "Agent execution was cancelled by user."})
        except Exception as e:
            logger.exception("Agent execution failed")
            await on_event("error", {"message": str(e)})
        finally:
            # Send a sentinel to close the queue gracefully
            await session.queue.put(None)
            
    # Start execution in the background
    session.task = asyncio.create_task(agent_task_runner())
    
    return {"session_id": session.id}

@app.post("/api/agent/stop/{session_id}")
async def stop_agent(session_id: str):
    if session_id in sessions:
        session = sessions[session_id]
        if session.task and not session.task.done():
            session.task.cancel()
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
    
    try:
        while True:
            # Wait for events from the agent
            event = await session.queue.get()
            if event is None:
                # Sentinel reached, execution finished
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    finally:
        # We don't cancel the task automatically on disconnect just in case it's a momentary network blip,
        # but you could add session cleanup here.
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, loop="none")
