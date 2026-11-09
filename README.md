# Trip Agent

A travel-planning agent that answers with **live data, not model memory**. Give it a destination and dates, and it looks up the weather forecast, public holidays, and location before answering.

Built with LangGraph and OpenAI, served as a FastAPI service on **Google Cloud Run**, traced in **Langfuse**, and evaluated with an **LLM-as-judge** pipeline. Currently scoped to travel within Egypt.

## Highlights

- **Tool-using agent:** a LangGraph ReAct agent chooses between geocoding, weather, and holiday tools, and chains them when a question needs more than one.
- **Production API:** a FastAPI service with structured requests, API-key auth, rate limiting, and a cap on agent steps to keep LLM costs bounded.
- **Deployed:** Docker image on Cloud Run, with all secrets in Google Secret Manager and a dedicated least-privilege service account.
- **Observable:** every run is traced in Langfuse, with the tool-call waterfall, latency, session IDs, and error tagging.
- **Tested and evaluated:** offline unit tests with mocked HTTP, CI on every push (ruff, mypy, pytest), and an LLM-as-judge eval set scoring accuracy, completeness, and helpfulness.

## How it works

```
POST /plan-trip  ──►  TripRequest  ──►  ReAct agent (gpt-4o-mini)
                                           │
                     ┌─────────────────────┼─────────────────────┐
                     ▼                     ▼                     ▼
              get_geocode          get_weather          get_public_holidays
              (Nominatim)          (Open-Meteo)          (Nager.Date)
                                           │
                                           ▼
                         answer + tools_called + session_id
                                 (traced in Langfuse)
```

Weather, holidays, and coordinates are facts that change, or that an LLM can confidently get wrong, so each one comes from a live, keyless public API.

## Project structure

```
trip-agent/
├── agent.py            # LLM + tools wired into a LangGraph ReAct agent
├── app.py              # CLI: interactive multi-turn, or one-shot with -q
├── settings.py         # validated config, fails fast on missing keys
├── models.py           # TripRequest → natural-language question
├── api/server.py       # FastAPI: /health, /plan-trip
├── prompts/system.py   # system prompt with today's date
├── tools/              # weather, geocoding, holidays, logging
├── evals/              # dataset, LLM-as-judge runner, results
├── tests/              # unit tests with mocked HTTP (respx)
├── .github/workflows/  # CI: lint, type check, tests
├── Dockerfile          # uv-based image serving the API on port 8000
└── docker-compose.yml  # local container run
```

## Quick start

Requires Python ≥3.11 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/maimayeg/trip-agent.git && cd trip-agent
uv sync --all-extras && source .venv/bin/activate
cp .env.example .env        # then fill in your keys
```

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes | The agent's LLM |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Yes | Tracing |
| `LANGFUSE_BASE_URL` | Yes | e.g. `https://cloud.langfuse.com` |
| `SERVICE_API_KEY` | API only | Value clients send in the `X-API-Key` header. Generate with `openssl rand -hex 32` |
| `RATE_LIMIT` / `RATE_WINDOW` | No | Requests per window, per key (default 10 per 60 s) |

**Run it:**

```bash
python app.py                                    # interactive CLI
python app.py -q "Weather in Luxor next week?"   # one-shot
uvicorn api.server:app --reload --port 8000      # API, docs at /docs
docker compose up --build                        # API in Docker on port 8000
```

## API

| Endpoint | Auth | Description |
|---|---|---|
| `GET /health` | None | Returns `{"status": "ok"}` |
| `POST /plan-trip` | `X-API-Key` | Runs the agent on a trip request |

```bash
curl -X POST http://localhost:8000/plan-trip \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SERVICE_API_KEY" \
  -d '{"destination": "Luxor", "start_date": "2026-11-20", "end_date": "2026-11-25", "interests": ["temples"]}'
```

**Request fields:** `destination` (required), `start_date` (required, `YYYY-MM-DD`), `end_date` (optional, not before the start), and `interests` (optional list).

**Response:**

```json
{
  "answer": "Here's what you need to know about your trip to Luxor...",
  "tools_called": ["get_public_holidays", "get_weather"],
  "session_id": "69ceeca9-6093-4fdb-964b-3a6bba6bf01c"
}
```

**Errors:** `401` bad or missing key · `422` invalid body · `429` rate limited · `500` agent failure (details are in Langfuse, not in the response).

## Security and cost controls

| Control | Detail |
|---|---|
| API key | Required on `/plan-trip`, checked with a constant-time comparison |
| Rate limit | 10 requests per minute per key by default; returns `429` above that |
| Agent step cap | `recursion_limit=10` prevents runaway tool loops |
| Input validation | Pydantic `TripRequest` rejects malformed requests |
| Instance cap | Cloud Run `--max-instances 1` |
| Spend cap | A dedicated OpenAI project with a monthly budget |
| Secrets | `.env` locally (git-ignored); Secret Manager in production; never baked into the image |

## Deployment (Cloud Run)

One-time setup: enable the Run, Secret Manager, Cloud Build, and Artifact Registry APIs. Then store the five variables above as secrets, and create a `trip-agent-sa` service account with `roles/secretmanager.secretAccessor` on those secrets only.

Deploy, or redeploy after changes:

```bash
gcloud run deploy trip-agent \
  --source . --region europe-west3 --port 8000 \
  --service-account trip-agent-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest,LANGFUSE_PUBLIC_KEY=LANGFUSE_PUBLIC_KEY:latest,LANGFUSE_SECRET_KEY=LANGFUSE_SECRET_KEY:latest,LANGFUSE_BASE_URL=LANGFUSE_BASE_URL:latest,SERVICE_API_KEY=SERVICE_API_KEY:latest \
  --max-instances 1 --concurrency 10 --timeout 120 \
  --allow-unauthenticated
```

The URL is public, but `/plan-trip` still requires the API key.

**Operations:**

- View logs: `gcloud run services logs read trip-agent --region europe-west3`
- Rotate a secret: `gcloud secrets versions add <NAME> --data-file=-`, then redeploy

## Testing, CI, and evals

```bash
pytest                       # offline; HTTP mocked with respx
python -m evals.run_evals    # LLM-as-judge, results in evals/results/
```

GitHub Actions runs `ruff check`, `ruff format --check`, `mypy`, and `pytest` on every push and pull request to `main`. No secrets are configured in CI, by design.

The eval runner sends every case in `evals/dataset.py` through the agent. A separate judge model then scores each answer from 1 to 5 on accuracy, completeness, and helpfulness, and prints averages along with the weakest cases.

## Known limitations

- Weather is forecast-only (up to 16 days ahead), with no historical data.
- Holidays don't yet distinguish nationwide from regional observances.
- Geocoding is scoped to Egypt.
- The API is single-turn, with no conversation memory between requests.
- There is one shared API key, and the rate limit is in memory, so it is only exact with a single instance.

## Roadmap

- [x] Structured `TripRequest` input
- [x] FastAPI endpoint with auth, rate limiting, and a step cap
- [x] CI: lint, type check, mocked tests
- [x] Docker + Cloud Run deployment with Secret Manager
- [ ] Harden all HTTP tool calls (timeouts, retries with backoff, connection reuse)
- [ ] Past-date weather handling and regional holiday labels
- [ ] Conversation memory for the API
- [ ] **Seasonal events tool**: a curated dataset of hyper-local travel windows such as harvests, migrations, and festivals (e.g. mango season in Ismailia)

## Tech stack

LangGraph · LangChain · OpenAI `gpt-4o-mini` · FastAPI · Pydantic · Langfuse · httpx · Open-Meteo · Nominatim · Nager.Date · uv · Ruff · mypy · pytest + respx · Docker · Google Cloud Run · Secret Manager · GitHub Actions
