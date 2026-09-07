"""
app.py — interactive CLI entry point for the trip agent.

Usage:
    python app.py                      # interactive loop — ask repeated questions
    python app.py -q "..."             # one-shot mode, answers and exits (for scripting)

Type 'exit', 'quit', or Ctrl+C/Ctrl+D to leave the interactive loop.

This will become a FastAPI endpoint once trip requests are structured
(destination/dates/interests) rather than free text — see README roadmap.
"""

import argparse
import sys
import uuid

from langfuse import get_client
from langfuse.langchain import CallbackHandler

from agent import agent, get_tools_called
from prompts.system import SYSTEM_PROMPT
from settings import settings  # fails fast on missing config, before anything else runs

langfuse = get_client()
langfuse_handler = CallbackHandler(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)


def ask(messages: list, span_name: str = "trip-agent-cli-run") -> dict:
    """
    Run one turn through the agent given the full message history so far
    (including the system prompt and any prior turns). Returns the answer,
    the tools called *this turn* only, and the full updated message list
    to pass into the next turn.
    """
    with langfuse.start_as_current_span(name=span_name) as span:
        span.update_trace(input={"question": messages[-1]["content"]})

        try:
            response = agent.invoke(
                {"messages": messages},
                config={"callbacks": [langfuse_handler]},
            )
        except Exception as e:
            span.update_trace(tags=["error"], output={"error": str(e)})
            raise

        updated_messages = response["messages"]
        # only the messages added this turn, so tool tagging reflects
        # this turn's activity rather than the whole conversation so far
        new_messages = updated_messages[len(messages):]
        tools_called = get_tools_called(new_messages)

        answer = updated_messages[-1].content
        span.update_trace(tags=tools_called, output={"answer": answer})

    return {"answer": answer, "tools_called": tools_called, "messages": updated_messages}


EXIT_WORDS = {"exit", "quit", "q", ":q"}


def run_interactive() -> None:
    print("Trip agent — ask a travel question (Egypt-scoped). Type 'exit' to quit.\n")

    session_id = str(uuid.uuid4())
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            break

        messages.append({"role": "user", "content": question})

        try:
            result = ask(messages, span_name=f"trip-agent-cli-turn-{session_id}")
        except Exception as e:
            print(f"Something went wrong: {e}\n", file=sys.stderr)
            messages.pop()  # drop the question that failed, so it's not stuck in history
            continue

        messages = result["messages"]
        print(f"\n{result['answer']}\n")
        print(f"(tools used: {', '.join(result['tools_called']) or 'none'})\n", file=sys.stderr)

    print("Goodbye.")


def run_once(question: str) -> None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    try:
        result = ask(messages)
    except Exception as e:
        print(f"Something went wrong: {e}\n", file=sys.stderr)
        return

    print(f"\n{result['answer']}\n")
    print(f"(tools used: {', '.join(result['tools_called']) or 'none'})\n", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Ask the trip agent travel questions."
    )
    parser.add_argument(
        "-q", "--question",
        help="Answer a single question and exit, instead of the interactive loop.",
    )
    args = parser.parse_args()

    if args.question:
        run_once(args.question)
    else:
        run_interactive()


if __name__ == "__main__":
    main()