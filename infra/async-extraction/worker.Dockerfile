# Worker image for the async extraction pipeline (scaffolding).
# Mirrors sidecar/Dockerfile but runs the SQS consumer instead of uvicorn.
# Build with context = ./sidecar:
#   docker build -f infra/async-extraction/worker.Dockerfile -t <ecr>/explify-worker ./sidecar
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    poppler-utils \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Long-polls SQS and processes one job at a time. Scale-to-zero is handled by the ECS
# service autoscaling on queue depth (see template.yaml); the process itself runs until
# the task is stopped (or until WORKER_IDLE_EXIT_SECONDS, if set, for self-drain).
CMD ["python", "-m", "worker.extraction_worker"]
