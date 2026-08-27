
# agent.py
import uuid
from dotenv import load_dotenv
load_dotenv()


from settings import settings   # fails fast here if anything's missing

from langfuse import get_client
from langfuse.langchain import CallbackHandler

langfuse = get_client()

langfuse_handler = CallbackHandler(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from tools.weather import get_weather
from tools.holidays import get_public_holidays
from tools.geocoding import get_geocode

from prompts.system import SYSTEM_PROMPT

llm = ChatOpenAI(model="gpt-4o-mini")

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
         "I'm going to paris next week, any holidays?",   # lowercase city
         "What's the weather in Fakecityxyz?",            # nonexistent city
         "I'm visiting New York next week, anything I should know?",
 
         # multi-tool
         "I want to visit Tokyo next week. Should I pack an umbrella and are there any public holidays?",
 
         # ambiguous
         "Is next week a good time to visit Berlin?",
 
         #baladna
         "I'm planning a trip to Asyut next month. Any recommendations?",
         "what is the weather like in Algharbiyya next month?"
 
 
         
     ]
    for q in questions:
        print(f"\n{'='*50}")
        print(f"Q: {q}")

        session_id = str(uuid.uuid4())

        with langfuse.start_as_current_span(name="trip-agent-run") as span:
            span.update_trace(session_id=session_id, input={"question": q})

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
            span.update_trace(tags=tools_called, output={"answer": response["messages"][-1].content})

        print(f"A: {response['messages'][-1].content}")
        print(f"Tools called: {tools_called}")


