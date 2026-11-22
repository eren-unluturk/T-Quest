# Build from the repo root:  docker build -f insights-sponsors/Dockerfile -t tquest-insights .
# UNTESTED: Docker was not available when this was written.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8002 APP_ENV=prod DATA_BACKEND=postgres
WORKDIR /app
RUN pip install fastapi "uvicorn[standard]" "psycopg[binary]" psycopg-pool pydantic pydantic-settings httpx
COPY shared /app/shared
COPY insights-sponsors /app/insights-sponsors
RUN useradd --system --uid 10001 --no-create-home app && chown -R app /app
USER app
ENV PYTHONPATH=/app/insights-sponsors/src TQUEST_SHARED_DIR=/app/shared
WORKDIR /app/insights-sponsors
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8002')+'/health',timeout=4)"
CMD ["sh", "-c", "uvicorn insights_sponsors.main:app --host 0.0.0.0 --port ${PORT}"]
