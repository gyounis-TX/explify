# Scale-to-zero Lambda image for the Explify FastAPI sidecar.
# Mirrors sidecar/Dockerfile (system deps + Python deps) but wraps the
# already-listening uvicorn server with the AWS Lambda Web Adapter so it
# can run as a Lambda Function URL with no app code changes.

FROM public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 AS adapter

FROM python:3.12-slim

# Same native deps the sidecar Dockerfile installs — required for tesseract,
# weasyprint (cairo/pango), pdf2image (poppler), etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    poppler-utils \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Lambda Web Adapter extension
COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

# Python deps copied from sidecar/
COPY sidecar/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Full sidecar tree
COPY sidecar/ .

# LWA config: forward Lambda events as HTTP to uvicorn on :8000
ENV AWS_LWA_PORT=8000
ENV AWS_LWA_READINESS_CHECK_PATH=/health
ENV AWS_LWA_INVOKE_MODE=response_stream
ENV AWS_LWA_PASS_THROUGH_PATH=/health

# Single uvicorn worker (Lambda runs one request per container).
CMD ["uvicorn", "main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
