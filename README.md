# Autonomous Interaction Management Framework for Dynamic Site Handling

A browser agent that carries out web tasks written in plain language, such as *"compare Pixel 10 across Amazon India and Flipkart"* or *"find the cheapest round trip flight from Delhi to Mumbai on Google Flights"*. It asks when a request is ambiguous, stays on approved websites, and does not bypass logins or CAPTCHAs.

Built with Python, Playwright, FastAPI, React and Groq-hosted LLMs.

## What it does

- **Understands the request.** An LLM planner works out the task (search, compare or book), the site, the search text and any constraints (rating, budget, condition). A rule-based planner takes over if the LLM is unavailable.
- **Asks when information is missing.** For example the Amazon region, flight dates, or an approved site when the user names one that is not approved. The run pauses and resumes once the user answers in the UI.
- **Compares products across sites.** Amazon and Flipkart results are normalised into one format (price, rating, rating count, availability) and ranked. Accessories and items that can't be bought yet are left out.
- **Browses on its own.** For other tasks, an agent loop reads the page, decides each click, typing step or extraction, and checks the goal against the page before stopping.
- **Stays on approved sites.** Navigation is limited to the site registry. Any click, redirect or popup that would leave it is blocked in the browser itself.
- **Detects CAPTCHA and login pages** during comparisons and stops there. It never tries to bypass them.
- **Remembers what worked.** Actions that achieved a goal, and routes between pages, are stored and recalled on later runs.

## How it works

```text
React UI (frontend/)
  └── REST + WebSocket
       └── FastAPI (server.py)
            ├── LLMTaskPlanner (agents/llm_planner.py), rule-based fallback in agents/task_planner.py
            │     └── asks the user when information is missing
            ├── compare  → sites/adapters.py → agents/answer_composer.py
            └── other    → router/task_router.py → ReasoningAgent (agents/reasoning_agent.py)
                               ├── GoalCompiler: turns the request into checkable requirements
                               ├── StateObserver + GoalVerifier: is the goal met, and what is missing?
                               ├── planner LLM: the next action on the current page
                               ├── BrowserController / BrowserExecutor: Playwright, with the site guard
                               └── MemoryState (ChromaDB) + NavigationGraph (SQLite)
```

Each step of the agent loop:
1. It observes the page and asks the goal verifier whether the goal is met.
   - If it is, the run stops with the answer read from the page.
   - If not, the verifier says what is still missing.
2. The planner LLM chooses the next action from the page's interactive elements and that feedback.
3. The action runs. A failed step gets an automatic recovery, and the agent stops if it makes no progress.

## Setup

Requires Python 3.10+ and Node.js 20.19+ (or 22.12+).

**Backend**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Create `.env` in the project root:
```env
GROQ_API_KEY=your_groq_api_key
# Optional: more keys, used in turn when one hits a rate limit
GROQ_API_KEY_2=
MODEL_NAME=qwen/qwen3.8-27b
# Optional: leave blank unless you have a vision-capable model
VISION_MODEL_NAME=
# Optional: how many runs of screenshots to keep (default 20)
MAX_SCREENSHOT_RUNS=20
```

Groq's free tier allows about 200,000 tokens per day **per account**, and one agent step uses about 3,500. Extra keys only help if they come from different accounts. `python scripts/check_groq_models.py` checks each configured key.

**Frontend**
```powershell
cd frontend
npm install
```

## Running

**Web UI (recommended).** Use two terminals:
```powershell
python server.py            # backend on http://localhost:8000
```
```powershell
cd frontend
npm run dev                 # UI on http://localhost:5173
```
To run the UI against a backend on another machine, create `frontend/.env` with `VITE_API_URL=http://<host>:8000`.

**Command line (development).** `main.py` runs the browsing agent directly, without the planner, clarifications or the approved-site restriction:
```powershell
python main.py "search running shoes on flipkart"
python main.py --headless --max-iterations 20 "your task"
```

### Example requests
```text
compare pixel 10 across amazon india and flipkart
compare pixel 10 across amazon india and flipkart with at least 4.3 star rating
compare iphone 16 prices on amazon                      (asks which region)
find the cheapest round trip flight from Delhi to Mumbai on google flights   (asks for dates)
search running shoes on flipkart and open the product page of the first result
search iphone 16 on ebay                                (not approved: offers approved sites)
```

## Approved sites

Amazon India, Amazon US, Flipkart and Google Flights, defined in `sites/registry.py` with their domains, country, currency and search URL. Price comparison works on sites with a product extractor, currently Amazon and Flipkart. Other approved sites are handled by the browsing agent.

## Project structure

```text
agents/     planning, goal checking, the agent loop, recovery, answer composition
browser/    Playwright control, DOM and page-state extraction, action execution
context/    prompt context building
llm/        Groq client (key rotation, rate-limit handling), intent parser
memory/     ChromaDB page and action memory, SQLite navigation graph
models/     Pydantic data models
router/     start strategy: direct search URL, site home page, or LLM-led
sites/      site registry and comparison extractors
frontend/   React + Vite UI
tests/      unit tests (no browser or API calls)
scripts/    live checks against real sites and the Groq API
docs/       earlier project documents
```

## Tests

Run the unit tests from the project root:
```powershell
python -m pytest
```
The tests live in `tests/`, and `pytest.ini` points pytest there, so no path is needed. The old `python -m unittest test_orchestration.py` no longer works, because the test files have moved. The unit tests don't use a browser or the Groq API. For a live end-to-end check:
```powershell
python scripts/live_agent_run.py "search running shoes on flipkart"
```

## Runtime data

These are all git-ignored:
- `memory_db/`: agent memory, persisted across runs. Delete it to start fresh.
- `screenshots/<run id>/`: one screenshot per step. Only the most recent runs are kept.
- `execution_history.log`: the CLI log.

## Known limitations

- **Site coverage.** Only registry sites are allowed. Adding a site means a registry entry, plus an extractor if it should take part in comparisons.
- **Offer fields.** Product condition is not extracted yet, and availability comes from Flipkart only. Amazon US has not been tested live.
- **Flight answers.** Each value in an answer is checked to be on the page, but not that all values come from the same flight.
- **CAPTCHA and login detection** covers comparisons only. The browsing agent stops through its step and progress limits instead.
- **Vision fallback** needs `VISION_MODEL_NAME`; without it, vision is not offered.

## Troubleshooting

- **The agent keeps waiting, or logs "rate limit".** A Groq key is out of quota. Add `GROQ_API_KEY_2` from another account, or wait for the reset time shown in the log.
- **`llama-3.3-70b-versatile` is retired.** The client switches to the default model. Clear a stale override with `Remove-Item Env:MODEL_NAME`.
- **ChromaDB: `range start index 10 out of range for slice of length 9`.** The environment has an older Chroma release. Activate `.venv` and run `python -m pip install -r requirements.txt`.
