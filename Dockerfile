FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e "."

COPY config.yaml .
COPY src/ src/
COPY data/ data/
COPY drafts/ drafts/

# Create non-root user and set ownership
RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --shell /bin/false appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
