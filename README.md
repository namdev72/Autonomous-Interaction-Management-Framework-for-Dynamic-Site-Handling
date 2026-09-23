# Autonomous Interaction Management Framework for Dynamic Site Handling

A browser agent that takes a task in plain language and carries it out on real websites. You can ask it to compare the Pixel 10 across Amazon and Flipkart, or to find the cheapest round-trip flight from Delhi to Mumbai, and it works through the sites the way a person would: searching, clicking, reading results, and reporting what it found.

## The problem

Websites change their layout often, build controls out of generic elements, and differ from one another in structure. Scripts written against a fixed page structure break when a site changes. An agent driven by an LLM adapts better, but it brings problems of its own: it can misread a request, act on incomplete information, report success without achieving the goal, or be led to an unrelated or unsafe site.

This project explores how to make such an agent reliable and safe enough for everyday tasks.

## How it works

A request goes through three stages.

**Planning.** An LLM reads the request and works out what is being asked: a search, a price comparison or a booking, which site to use, what to search for, and any constraints such as a budget or minimum rating. Code then checks the plan against a registry of approved sites. If something essential is missing, such as travel dates or which Amazon region to use, the agent asks the user before it starts.

**Execution.** Product searches and price comparisons go to site-specific extractors, which read product listings from each site and normalise them into one format for ranking. Everything else goes to a general browsing agent that runs in a loop: questions a list of results cannot answer, such as a product's specifications, as well as flights and other browsing. On each step, the agent reads the current page, checks whether the goal has been met, and if not, decides the next action: a click, typing, scrolling or extracting text.

**Verification.** A separate check, not the step that acts, decides when the task is done. It compares the page against requirements derived from the original request. When it rejects a result, it says what is still missing, and the agent uses that to decide its next step. Answers are built only from text that appears on the page.

```text
React UI ── WebSocket ── FastAPI server
                            │
                      LLM task planner ── asks the user when information is missing
                            │
              ┌─────────────┴─────────────┐
      product extractors           browsing agent loop
     (Amazon, Flipkart)            observe → verify → plan → act
                                          │
                                   Playwright browser
                                   (limited to approved sites)
```

## Design decisions

**Controlled navigation.** The agent can only visit approved sites. This is enforced in the browser itself, so a link, redirect or popup that leads elsewhere is blocked even if the LLM chose it. The agent never tries to get past a login or CAPTCHA page, and comparisons detect these pages and stop.

**Ask rather than guess.** When a request is ambiguous, a question to the user is cheaper than a wrong answer, so the planner is built to recognise missing information and ask for it.

**Verify against the page.** The agent does not decide for itself that it is finished. Completion is judged against the original request, using what is actually on the page.

**Memory.** Actions that achieved a goal, and the routes between pages, are stored and reused on later runs, so repeated tasks on the same site need fewer steps.

**Cost awareness.** Every step uses LLM tokens, so prompts are kept small, unchanged pages are not re-checked, and multiple API keys can be rotated when one hits its rate limit.

**Expect the LLM to misbehave.** A model that answers in prose where JSON was asked for, or does not answer at all, is treated as a normal condition rather than a crash: the JSON is recovered from the reply where possible, the model is asked once more otherwise, and a run whose LLM calls keep failing stops and says so instead of looping. Time spent waiting on the LLM does not count as the agent failing to make progress.

## Tech stack

Python, Playwright, FastAPI, React with Vite, Groq-hosted LLMs (Qwen), ChromaDB and SQLite.

## Status

Working end to end:
- product search and comparison on Amazon (India and US) and Flipkart;
- flight search on Google Flights;
- general browsing tasks on approved sites;
- clarification questions in the UI.

In progress:
- letting users approve sites beyond the fixed registry;
- a generic product extractor so any shopping site can take part in comparisons;
- extracting product condition;
- a vision model for pages the DOM alone doesn't describe well.

## Getting started

You need Python 3.10+ and Node.js 20.19+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
cd frontend; npm install; cd ..
```

Create a `.env` file in the project root with a Groq API key:

```env
GROQ_API_KEY=your_key
# Optional: extra keys, from other Groq accounts, used when one hits its limit
GROQ_API_KEY_2=
```

Start the backend and the UI in two terminals, then open http://localhost:5173:

```powershell
python server.py
```
```powershell
cd frontend; npm run dev
```

Run the unit tests from the project root with `python -m pytest`. The tests are in `tests/`; the old `python -m unittest test_orchestration.py` command no longer works.

## Repository layout

```text
agents/     planning, goal verification and the agent loop
browser/    Playwright control and page reading
sites/      approved-site registry and product extractors
router/     how a task starts: search URL, site home page, or LLM-led
memory/     vector memory (ChromaDB) and navigation graph (SQLite)
llm/        LLM client with key rotation
frontend/   React UI
tests/      unit tests
scripts/    live checks against real sites and the Groq API
docs/       earlier project documents
```
