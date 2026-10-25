
import re
from pathlib import Path

import cohere
from dotenv import dotenv_values
from rich import print


# =========================================================
# 1. PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

env_vars = dotenv_values(ENV_PATH)
CohereAPIKey = env_vars.get("CohereAPIKey")

co = cohere.Client(api_key=CohereAPIKey) if CohereAPIKey else None


# =========================================================
# 2. SUPPORTED TASKS
# =========================================================

funcs = [
    "exit",
    "general",
    "realtime",
    "open",
    "close",
    "play",
    "generate image",
    "system",
    "content",
    "google search",
    "youtube search",
    "reminder",
]


# =========================================================
# 3. CLASSIFICATION INSTRUCTIONS
# =========================================================

preamble = """
You are the Decision-Making Model for a personal AI assistant.

Do not answer the user's question. Classify it into one or more
commands. Return only commands, separated by commas.

SUPPORTED COMMANDS:

1. general (query)
   Use for normal conversation, explanations, coding questions,
   calculations, and questions that do not need current web data.

2. realtime (query)
   Use when the user asks for current news, recent updates,
   current public-figure information, or other time-sensitive facts.

3. open (application or website)
   Use when the user asks to open an app or website.

4. close (application or website)
   Use when the user asks to close an app or website.

5. play (song name)
   Use when the user asks to play a song.

6. generate image (image description)
   Use when the user requests image generation.

7. reminder (date, time, and reminder message)
   Use when the user requests a reminder.

8. system (task)
   Use for system controls such as volume up, volume down, mute,
   and unmute.

9. content (topic)
   Use when the user asks you to write content, code, an email,
   an application, or similar material.

10. google search (topic)
    Use when the user explicitly asks to search Google.

11. youtube search (topic)
    Use when the user explicitly asks to search YouTube.

12. exit
    Use when the user says goodbye or asks to end the assistant.

RULES:
- Preserve the user's original query after the command label.
- Do not answer the query.
- Do not add explanations, markdown, or quotation marks.
- For multiple tasks, return one command per task, separated by commas.
- Example: "open chrome and close notepad"
  -> open chrome, close notepad
- Example: "open chrome and explain Python"
  -> open chrome, general explain Python
- Example: "search Google for AI news"
  -> google search AI news
- Example: "what is Python?"
  -> general what is Python?
- Example: "what is today's latest technology news?"
  -> realtime what is today's latest technology news?
- If uncertain, use general (query).
"""


# =========================================================
# 4. CLASSIFICATION EXAMPLES
# =========================================================

ChatHistory = [
    {
        "role": "User",
        "message": "How are you?",
    },
    {
        "role": "Chatbot",
        "message": "general How are you?",
    },
    {
        "role": "User",
        "message": "Open Chrome and Firefox.",
    },
    {
        "role": "Chatbot",
        "message": "open Chrome, open Firefox",
    },
    {
        "role": "User",
        "message": "Open Chrome and tell me about iron man.",
    },
    {
        "role": "Chatbot",
        "message": "open Chrome, general tell me about iron man",
    },
    {
        "role": "User",
        "message": "Play Let Her Go.",
    },
    {
        "role": "Chatbot",
        "message": "play Let Her Go",
    },
    {
        "role": "User",
        "message": "Bye.",
    },
    {
        "role": "Chatbot",
        "message": "exit",
    },
]


# =========================================================
# 5. RESPONSE PARSING
# =========================================================

def _parse_tasks(response_text: str) -> list[str]:
    """Extract supported commands from Cohere's text response."""

    if not isinstance(response_text, str):
        return []

    response_text = response_text.replace("\n", " ").strip()

    # Split only where another supported command appears.
    # This helps preserve commas inside the user's actual query.
    command_pattern = "|".join(
        re.escape(command)
        for command in sorted(funcs, key=len, reverse=True)
    )

    parts = re.split(
        rf",\s*(?=(?:{command_pattern})(?:\s|$))",
        response_text,
        flags=re.IGNORECASE,
    )

    valid_tasks = []

    for part in parts:
        task = part.strip().strip('"').strip("'")

        for command in sorted(funcs, key=len, reverse=True):
            if (
                task.lower() == command
                or task.lower().startswith(command.lower() + " ")
            ):
                valid_tasks.append(task)
                break

    return valid_tasks


# =========================================================
# 6. MAIN CLASSIFIER
# =========================================================

def is_realtime_query(prompt: str) -> bool:
    """Detect queries that likely require up-to-date information."""

    text = prompt.lower().strip()

    realtime_patterns = [
        r"\btoday\b",
        r"\bright now\b",
        r"\bcurrently\b",
        r"\bcurrent\b",
        r"\blatest\b",
        r"\brecent\b",
        r"\bbreaking news\b",
        r"\bthis week\b",
        r"\bthis month\b",
        r"\bcurrent news\b",
        r"\bweather\b",
        r"\bforecast\b",
        r"\bstock price\b",
        r"\bshare price\b",
        r"\bexchange rate\b",
        r"\bwho is the current\b",
        r"\bwhat happened\b",
        r"\btoday's news\b",
    ]

    return any(re.search(pattern, text) for pattern in realtime_patterns)

def FirstLayerDMM(prompt: str = "test") -> list[str]:
    """Classify a user query into supported assistant commands."""

    if not isinstance(prompt, str) or not prompt.strip():
        return []

        # Route obvious time-sensitive questions directly.
    if is_realtime_query(prompt):
        return [f"realtime {prompt.strip()}"]

    if co is None:
        print(
            "[red]CohereAPIKey is missing from the project's .env file.[/red]"
        )
        return [f"general {prompt.strip()}"]

    try:
        response = co.chat(
            model="command-a-03-2025",
            message=prompt.strip(),
            temperature=0.2,
            chat_history=ChatHistory,
            prompt_truncation="OFF",
            connectors=[],
            preamble=preamble,
        )

        # The standard Cohere ChatResponse exposes generated text
        # through its .text attribute.
        response_text = getattr(response, "text", "")

        tasks = _parse_tasks(response_text)

        if tasks:
            return tasks

        # Safe fallback: do not recursively call the classifier.
        print(
            "[yellow]Classifier returned no supported command. "
            "Using general fallback.[/yellow]"
        )
        return [f"general {prompt.strip()}"]

    except Exception as error:
        print(f"[red]Cohere classification error: {error}[/red]")
        return [f"general {prompt.strip()}"]


# =========================================================
# 7. DIRECT TEST
# =========================================================

if __name__ == "__main__":
    print("[bold cyan]ULTRON AI - Task Classifier[/bold cyan]")
    print("Type 'exit' to stop testing.")

    while True:
        try:
            query = input("\nYou: ").strip()

            if query.lower() in {"exit", "quit"}:
                print("Classifier test ended.")
                break

            if query:
                print(FirstLayerDMM(query))

        except (KeyboardInterrupt, EOFError):
            print("\nClassifier test ended.")
            break