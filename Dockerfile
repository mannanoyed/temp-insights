# meet-insights — RunPod serverless handler
# CPU-only, Gemini-based meeting analysis

FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY runpod_handler.py .
COPY main.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "runpod_handler.py"]
