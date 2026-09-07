from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.prebuilt import create_react_agent

from prompts.system import SYSTEM_PROMPT
from settings import settings
from tools.geocoding import get_geocode
from tools.holidays import get_public_holidays
from tools.weather import get_weather

load_dotenv()  # kept for any lib that reads os.environ directly; settings.py
                # already loads .env itself, so this is now a safety net,
                # not a hard requirement for settings validation to work.

Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)
langfuse_handler = CallbackHandler()

llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key)

agent = create_react_agent(
    llm,
    tools=[get_weather, get_public_holidays, get_geocode])


def get_tools_called(messages) -> list[str]:
    """Pull the distinct tool names the agent actually invoked out of the run's messages."""
    names = set()
    for m in messages:
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            names.update(tc["name"] for tc in tool_calls)
    return sorted(names)


if __name__ == "__main__":
    questions = [
        # happy path
        "I want to visit Tokyo next week. Should I pack an umbrella?",
        "Any public holidays in Germany this month?",
        "What's the weather like in Paris next week?",

        # edge cases
        "I'm going to paris next week, any holidays?",
        "What's the weather in Fakecityxyz?",
        "I'm visiting New York next week, anything I should know?",

        # multi-tool
        "I want to visit Tokyo next week. Should I pack an umbrella and "
        "are there any public holidays?",

        # ambiguous
        "Is next week a good time to visit Berlin?",
    ]

    for q in questions:
        print(f"\n{'='*50}")
        print(f"Q: {q}")
        response = agent.invoke(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": q}
                ]
            },
            config={"callbacks": [langfuse_handler]}
        )
        tools_called = get_tools_called(response["messages"])
        answer = response["messages"][-1].content
        print(f"A: {answer}")
        print(f"(tools used: {', '.join(tools_called) or 'none'})")