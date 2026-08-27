# Trip Agent

A LangGraph ReAct agent that answers travel-planning questions — weather forecasts, public holidays, and location lookups — using live data instead of relying on an LLM's memory. Traced with Langfuse, evaluated with an LLM-as-judge pipeline.

Currently scoped to **domestic travel within Egypt** (see [Roadmap](#roadmap) for the seasonal-events direction this is heading).

## What it does

Given a question like *"I want to visit Luxor next week, should I pack an umbrella?"*, the agent:

1. Resolves the city name to coordinates (geocoding)
2. Pulls a live weather forecast for those coordinates
3. Reasons over the result and answers in plain language

It can also look up public holidays and chain multiple tools together for questions that need more than one piece of information.

## Architecture

```
trip-agent/
├── agent.py              # wires the LLM + tools into a LangGraph ReAct agent
├── prompts/
│   └── system.py          # system prompt (injects today's date, Egypt scope)
├── tools/
│   ├── weather.py          # forecast lookup via Open-Meteo
│   ├── geocoding.py        # city → lat/lon via Nominatim (restricted to Egypt)
│   ├── holidays.py         # public holidays via Nager.Date
│   └── logger.py           # shared structured logging setup
├── evals/
│   ├── dataset.py           # eval question set with categories
│   └── run_evals.py         # runs the agent + an LLM judge over the dataset
├── tests/
│   ├── test_weather.py
│   └── test_holidays.py
├── pyproject.toml
└── .env.example
```

**Why tools instead of LLM knowledge:** weather, holidays, and coordinates are facts that change or that an LLM can hallucinate with confidence. Each is backed by a live API call rather than trusted to the model's training data.

## Setup

**Requirements:** Python ≥3.11

```bash
# clone and enter the repo
git clone <repo-url>
cd trip-agent

# create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# install dependencies
pip install -e .
# for running tests and evals:
pip install -e ".[dev]"
```

Copy the environment template and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Used by the agent's LLM (`gpt-4o-mini`) |
| `LANGFUSE_PUBLIC_KEY` | Yes | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | Yes | Langfuse project secret key |
| `LANGFUSE_HOST` | Yes | Langfuse instance URL (e.g. `https://cloud.langfuse.com`) |

No API key is needed for weather (Open-Meteo), geocoding (Nominatim), or holidays (Nager.Date) — all three are free, keyless public APIs.

## Running it

```bash
python agent.py
```

This runs a fixed set of sample questions through the agent and prints each answer to stdout, with full traces sent to Langfuse.

## Running tests

```bash
pytest
```

Unit tests currently call the live weather and holidays APIs directly — network access is required to run them. (Mocking the HTTP layer is on the roadmap.)

## Running evals

```bash
python -m evals.run_evals
```

Runs every question in `evals/dataset.py` through the agent, then grades each answer with a separate LLM-as-judge call on accuracy, completeness, and helpfulness (1–5). Results are saved to `evals/results/<timestamp>.json`, with a summary printed to the console — average scores per dimension and the lowest-scoring cases.

## Observability

Every agent run is traced in [Langfuse](https://langfuse.com), including:
- The full tool-call waterfall (which tools ran, in what order, with what latency)
- A `session_id` per run
- Tags for which tools were actually invoked

## Known limitations

- Weather is forecast-only — it cannot answer questions about past weather.
- Holiday data currently doesn't distinguish nationwide vs. regional/subdivision holidays for countries where that applies.
- Geocoding is restricted to Egypt; questions about other countries won't resolve.
- No deployment target yet — this runs as a local script only.

## Roadmap

- [ ] Harden all HTTP tool calls (timeouts, error handling, connection reuse) — currently only partially done in `weather.py`
- [ ] Fix past-date weather handling and regional-holiday labeling
- [ ] Structured trip input (`TripRequest` pydantic model: destination, dates, interests) instead of free-text questions
- [ ] FastAPI endpoint wrapping the agent
- [ ] CI: lint, type check, mocked tests
- [ ] Dockerfile + deployment (Cloud Run)
- [ ] **Seasonal events tool** — a curated dataset of hyper-local seasonal travel windows (harvests, migrations, local festivals) as an alternative lens to generic public holidays, e.g. mango season in Ismailia

## Tech stack

- [LangGraph](https://github.com/langchain-ai/langgraph) — agent orchestration (`create_react_agent`)
- [LangChain](https://github.com/langchain-ai/langchain) — tool interface
- OpenAI `gpt-4o-mini` — the agent's LLM
- [Langfuse](https://langfuse.com) — tracing and observability
- [httpx](https://www.python-httpx.org/) — HTTP client for tool APIs
- [Open-Meteo](https://open-meteo.com/), [Nominatim](https://nominatim.org/), [Nager.Date](https://date.nager.at/) — data sources
