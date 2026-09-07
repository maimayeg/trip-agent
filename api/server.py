"""
api/server.py — FastAPI entry point for the trip agent.

Run from the project root with:
    uvicorn api.server:app --reload

Then:
    curl -X POST http://localhost:8000/plan-trip \
        -H "Content-Type: application/json" \
        -d '{"question": "Weather in Luxor next week?"}'

Note: each request is currently a single, independent turn — there's no
conversation memory across HTTP calls yet (unlike app.py's interactive
loop). Adding that means deciding how to store session state (in-memory
dict for a demo, a real store for anything beyond that) — worth doing
once TripRequest (destination/dates/interests) replaces free-text
questions, rather than bolting it on twice.
"""

import os
import sys
import uuid

from fastapi import FastAPI, HTTPException
from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel

# This file lives in api/, but agent.py, settings.py, prompts/, and tools/
# live in the project root. Add the root to sys.path so the imports below
# (from agent import ..., from settings import ...) resolve correctly
# regardless of where uvicorn is invoked from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# These genuinely must come after the sys.path fix above — they're local
# project modules, not installed packages, so noqa is correct here.
from agent import agent, get_tools_called  # noqa: E402
from models import TripRequest  # noqa: E402
from prompts.system import SYSTEM_PROMPT  # noqa: E402
from settings import settings  # noqa: E402  (fails fast on missing config)

Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)
langfuse = get_client()
langfuse_handler = CallbackHandler()

app = FastAPI(
    title="Trip Agent API",
    description="Ask travel questions about Egypt — weather, holidays, and locations.",
    version="0.1.0",
)


class TripAnswerResponse(BaseModel):
    answer: str
    tools_called: list[str]
    session_id: str


@app.get("/health")
def health():
    """Basic liveness check — does not verify OpenAI/Langfuse connectivity."""
    return {"status": "ok"}


@app.post("/plan-trip", response_model=TripAnswerResponse)
def plan_trip(trip: TripRequest):
    session_id = str(uuid.uuid4())
    question = trip.to_question()

    with langfuse.start_as_current_observation(name="trip-agent-api-run", as_type="span") as span:
        with propagate_attributes(session_id=session_id):
            try:
                response = agent.invoke(
                    {
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": question},
                        ]
                    },
                    config={"callbacks": [langfuse_handler]},
                )
            except Exception as e:
                span.update(level="ERROR", status_message=str(e))
                # Don't leak internals to the client — real error is in the
                # Langfuse trace + server logs.
                raise HTTPException(
                    status_code=500, detail="Failed to process the request."
                ) from e

            answer = response["messages"][-1].content
            tools_called = get_tools_called(response["messages"])
            span.set_trace_io(input=trip.model_dump(mode="json"), output={"answer": answer})

    return TripAnswerResponse(answer=answer, tools_called=tools_called, session_id=session_id)