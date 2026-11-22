# Build from the repo root:  docker build -f data-platform/Dockerfile -t tquest-data-platform .
# UNTESTED: Docker was not available when this was written.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8001 APP_ENV=prod
WORKDIR /app
RUN pip install fastapi "uvicorn[standard]" "psycopg[binary]" python-dotenv pydantic httpx
COPY shared /app/shared
COPY data-platform /app/data-platform
RUN useradd --system --uid 10001 --no-create-home app && chown -R app /app
USER app
ENV PYTHONPATH=/app/data-platform/src TQUEST_SHARED_DIR=/app/shared
WORKDIR /app/data-platform
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8001')+'/health',timeout=4)"
CMD ["sh", "-c", "uvicorn data_platform.app:app --host 0.0.0.0 --port ${PORT}"]
