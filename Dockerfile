FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e "."

COPY config.yaml .
COPY src/ src/
COPY data/ data/
COPY drafts/ drafts/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
