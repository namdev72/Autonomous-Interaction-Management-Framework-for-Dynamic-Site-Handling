# Autonomous Web Browser Agent Framework

An intelligent, autonomous web agent framework that translates natural language instructions into concrete browser actions. Built with Python, Playwright, and powered by Groq LLMs, this framework enables agents to navigate, scrape, and interact with dynamic websites intelligently.

## 🚀 Features

- **Natural Language Task Execution**: Give the agent tasks like *"go to books.toscrape.com and extract the price of a light in the attic"* and it handles the rest.
- **Headful or Headless Browsing**: Watch the agent work in real-time or run it silently in the background.
- **Intelligent DOM Extraction**: Automatically identifies and targets interactive elements in the DOM using an injected Playwright ID system.
- **Memory & History Tracking**: Keeps a history of past actions to avoid repetitive loops and maintain context during long tasks.
- **Groq LLM Integration**: Uses lightning-fast Groq models (defaults to `llama-3.3-70b-versatile`) for reasoning and deciding the next browser action.

## 🛠️ Technology Stack

- **Python 3.8+**
- **Playwright**: For robust and reliable browser automation.
- **Groq API**: High-speed inference using LLaMA models.
- **Loguru**: Clean, colorful, and rotating execution logs.
- **Pydantic**: Structured action models and validation.
- **BeautifulSoup4 & LXML**: For HTML parsing and DOM manipulation.

## 📁 Folder Structure

```
├── agents/             # Core reasoning logic (e.g., ReasoningAgent)
├── browser/            # Playwright interaction layers (actions, DOM extraction, controllers)
├── context/            # Constructs structural and visual context of the page for the LLM
├── llm/                # LLM client configuration, prompting, and intent parsing
├── memory/             # Action history tracking to maintain state and avoid loops
├── models/             # Pydantic schemas representing structured actions
├── main.py             # CLI entry point for the framework
└── requirements.txt    # Project dependencies
```

## ⚙️ Prerequisites

1. **Python 3.8 or higher** installed on your system.
2. A **Groq API Key** (You can obtain one from the [Groq Console](https://console.groq.com)).

## 📦 Installation

1. **Navigate to the project directory**:
   ```bash
   cd Autonomous-Interaction-Management-Framework-for-Dynamic-Site-Handling
   ```

2. **Create and activate a virtual environment (Recommended)**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # .\venv\Scripts\activate # On Windows
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install
   ```

5. **Configure Environment Variables**:
   Create a `.env` file in the root directory and add your Groq API key:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   MODEL_NAME=llama-3.3-70b-versatile   # Optional, this is the default
   ```

## 🚀 Usage

You can run the agent in two modes using the `main.py` entry point.

### Interactive CLI Mode
If you run the script without any arguments, it will launch an interactive prompt where you can enter your task:

```bash
python main.py
```

### Single Command Mode
You can pass your task directly as command-line arguments:

```bash
python main.py "open amazon website and search for iphone 16"
```

## 📜 Logging
The framework utilizes `loguru` for extensive logging. All execution logs and agent reasoning steps are printed to the console and automatically saved to `execution_history.log` (rotates at 10 MB) in the project root.
