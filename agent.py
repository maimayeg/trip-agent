# agent.py
from dotenv import load_dotenv
load_dotenv() 

from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler()

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from tools.weather import get_weather
from tools.holidays import get_public_holidays

from prompts.system import SYSTEM_PROMPT


llm = ChatOpenAI(model="gpt-4o-mini")




agent = create_react_agent(
    llm,
    tools=[get_weather, get_public_holidays])   

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
        print(f"A: {response['messages'][-1].content}")
