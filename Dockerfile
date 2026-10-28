# ---------------------------------------------------------------------------
# Dockerfile: the recipe for building an "image" of the trip agent.
# An image is a frozen box with Python, your dependencies and your code
# inside. Every container started from it behaves exactly the same.
# ---------------------------------------------------------------------------

# 1. Start from a small official image that already has Python installed.
FROM python:3.12-slim

# 2. Copy the `uv` tool in from its official image (same tool CI uses).
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv

# 3. All following commands run inside /app in the box.
WORKDIR /app

# PYTHONUNBUFFERED=1 -> logs show up immediately instead of being held back.
# UV_LINK_MODE=copy  -> avoids a harmless uv warning inside Docker.
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# 4. Install dependencies FIRST, using only the two files that list them.
#    Docker caches each step: as long as these two files don't change,
#    rebuilding after a code edit skips this slow step.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 5. Now copy your code in (.dockerignore decides what is left out).
COPY . .
RUN uv sync --frozen

# 6. Use the installed environment's python/uvicorn by default.
ENV PATH="/app/.venv/bin:$PATH"

# 7. The API listens on port 8000.
EXPOSE 8000

# 8. What runs when the container starts: your FastAPI server.
#    --host 0.0.0.0 makes it reachable from outside the box (your Mac).
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
