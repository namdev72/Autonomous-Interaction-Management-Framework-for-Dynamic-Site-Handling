# Autonomous Web Browser Agent Framework

An autonomous browser-agent framework that translates natural language instructions into concrete browser actions. It uses Python, Playwright, Groq-compatible OpenAI APIs, structured memory, and an explicit orchestration loop for dynamic site handling.

## Features

- Natural language task execution through a CLI entry point.
- Headful or headless Chromium browsing with Playwright.
- Viewport-focused DOM extraction with injected `data-playwright-id` targets.
- Shadow DOM and iframe-aware element extraction.
- Structured action execution results with URL, error, recovery hint, screenshot, and extracted value fields.
- Deterministic recovery policy for failed actions and repeated loops.
- Verified completion: `done` actions are checked against the original user goal before stopping.
- Semantic memory indexing with ChromaDB for current-session page context recall.
- Optional vision fallback for coordinate-based click recovery.
- Deterministic task planning with approved-site and region clarification.
- Public product comparison for Amazon India, Amazon US, and Flipkart.
- Interactive follow-up questions over the WebSocket session.

## Architecture

The project features a decoupled architecture with a React-based web interface communicating with a Python FastAPI backend, which orchestrates the autonomous browser agent.

```text
React Frontend (Vite)
  └── WebSockets & REST
       └── FastAPI Backend (server.py)
            └── agents.reasoning_agent.ReasoningAgent
                 ├── browser.controller.BrowserController (Playwright)
                 ├── llm.llm_client.LLMClient (Groq LLM)
                 ├── memory.history.MemoryState (ChromaDB)
                 └── context.context_builder.ContextBuilder
```

1. **Frontend**: A React/Vite web application that provides a real-time terminal-like interface. It sends tasks to the backend and listens to real-time agent execution logs via WebSockets.
2. **Backend**: A FastAPI server (`server.py`) that initializes the agent session and handles the `asyncio` event loops required by Playwright and Uvicorn.
3. **Agent Loop**:
   - Parses the user intent and opens the target website.
   - Extracts interactive DOM elements and injects `data-playwright-id` tags.
   - Builds compact context (DOM + recent semantic memory) and sends it to the LLM.
   - Decides the next structured action (`AgentAction`).
   - Executes the action via Playwright, applies automatic recovery for failures, and repeats until the goal is verified as `done`.
4. **Comparison Flow**:
   - Classifies the task and asks for an Amazon region or preferred site when needed.
   - Builds deterministic URLs only for approved domains.
   - Extracts public product offers into a common schema and ranks them by price and constraints.
   - Stops at login or human verification pages and reports the required user handoff; it does not bypass those controls.

## Installation

You need both Python and Node.js installed on your system.

### 1. Backend Setup (Python)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Create a `.env` file in the project root:
```env
GROQ_API_KEY=your_groq_api_key_here
MODEL_NAME=qwen/qwen3.8-27b
VISION_MODEL_NAME=
```

### 2. Frontend Setup (Node.js)
Open a new terminal or use the same one:
```powershell
cd frontend
npm install
```

## Usage

You can run the project either through the full Web UI (recommended) or directly via the CLI.

### Option A: Run with Web UI (Frontend + Backend)

You will need two separate terminal windows.

**Terminal 1: Start the Backend API**
Make sure your virtual environment is activated, then run:
```powershell
python server.py
```
*(The backend will start on `http://localhost:8000`)*

**Terminal 2: Start the Frontend UI**
```powershell
cd frontend
npm run dev
```
*(The UI will be accessible at `http://localhost:5173`. Enter your task there to watch the agent work in real-time.)*

The UI talks to `http://localhost:8000` by default. To use a backend elsewhere, create `frontend/.env` with `VITE_API_URL=http://<host>:8000` and restart `npm run dev`.

### Option B: Run in CLI Mode

If you prefer to run the agent headlessly or directly from the terminal without the UI:

Interactive mode:
```bash
python main.py
```

Single task:
```bash
python main.py "go to books.toscrape.com and extract the price of a light in the attic"
```

Useful runtime flags:
```bash
python main.py --headless --max-iterations 20 --model qwen/qwen3.8-27b "open wikipedia and search for Samsung"
```

### Interactive comparison examples

Use the Web UI for requests such as:

```text
compare iPhone 16 prices on Amazon India and Flipkart
compare iPhone 16 prices on Amazon
check ticket price for a flight from Delhi to London
```

The UI asks a follow-up when the Amazon region or a preferred flight website is ambiguous. Comparison runs use approved public-site adapters and return normalized offers, price, rating, source URL, and warnings.

The current approved sites are Amazon India, Amazon US, Flipkart, and Google Flights. Site policy is defined in `sites/registry.py`; adding a domain requires an explicit policy and adapter.

## Tests

Run deterministic orchestration tests:

```bash
python -m unittest test_orchestration.py
```

Run a syntax compile pass:

```bash
python -m compileall agents browser context llm memory models main.py test_orchestration.py
```

## Notes

- Runtime memory is written to `memory_db/` and ignored by Git.
- Screenshots are written to `screenshots/`.
- Full browser runs require a valid `GROQ_API_KEY`.
- A vision model is optional. Leave `VISION_MODEL_NAME` blank unless your Groq account provides a vision-capable model; DOM-based actions continue to work without it.

## Troubleshooting

If startup reports that `llama-3.3-70b-versatile` is retired, the client automatically replaces it with the configured default. Clear a stale override from the current PowerShell session before restarting the agent:

```powershell
Remove-Item Env:MODEL_NAME -ErrorAction SilentlyContinue
```

If ChromaDB reports `range start index 10 out of range for slice of length 9`, the active Python environment has an older Chroma release than the existing memory schema. Activate `.venv` and reinstall the pinned dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The memory database does not need to be deleted.
