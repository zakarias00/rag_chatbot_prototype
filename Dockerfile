# syntax=docker/dockerfile:1
FROM python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY app.py ./
COPY data/ ./data/


RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
        PIP_CERT=/run/secrets/proxy_ca python -m pip install --no-cache-dir -e .; \
    else \
        python -m pip install --no-cache-dir -e .; \
    fi \
    && python -m src.rag.ingestion \
    && python -m src.rag.index build

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
