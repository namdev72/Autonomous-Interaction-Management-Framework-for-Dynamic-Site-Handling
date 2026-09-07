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

## Architecture

```text
main.py
  -> agents.reasoning_agent.ReasoningAgent
    -> llm.intent_parser.IntentParser
    -> browser.controller.BrowserController
    -> browser.dom_extractor.DOMExtractor
    -> context.context_builder.ContextBuilder
    -> llm.llm_client.LLMClient
    -> browser.actions.BrowserExecutor
    -> agents.recovery_policy.RecoveryPolicy
    -> agents.goal_verifier.GoalVerifier
    -> memory.history.MemoryState
```

The agent loop runs as:

1. Parse the user intent and resolve a starting URL.
2. Open the browser and wait for initial page load.
3. Extract visible interactive elements from the page and frames.
4. Build compact context for the LLM.
5. Add recent actions, action results, extracted data, and semantic memory.
6. Ask the LLM for the next structured `AgentAction`.
7. Verify completion if the action is `done`.
8. Execute the action through Playwright.
9. Apply deterministic recovery or vision fallback if execution fails.
10. Persist action/result memory and repeat until verified completion or max iterations.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
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

## Usage

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
