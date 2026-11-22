# Build from the repo root:  docker build -f game-engine/Dockerfile -t tquest-game-engine .
# UNTESTED: Docker was not available when this was written.
# Database mode is read-only unless GE_ALLOW_DB_WRITES=1 (see game-engine/README.md); on the demo host it targets the DEMO database only.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8003 APP_ENV=prod
WORKDIR /app
COPY game-engine/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY shared /app/shared
COPY game-engine /app/game-engine
RUN useradd --system --uid 10001 --no-create-home app && chown -R app /app
USER app
ENV PYTHONPATH=/app/game-engine/src TQUEST_SHARED_DIR=/app/shared
WORKDIR /app/game-engine/src
EXPOSE 8003
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8003')+'/healthz',timeout=4)"
CMD ["sh", "-c", "uvicorn game_engine.app:app --host 0.0.0.0 --port ${PORT}"]
