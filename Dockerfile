# =========================================
# meet-insights — RunPod serverless handler
# Gemini-based meeting analysis
# =========================================

FROM python:3.11-slim

WORKDIR /app

# System deps (minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# App code
COPY runpod_handler.py .
COPY main.py .

# Runtime env
ENV PYTHONUNBUFFERED=1
# GEMINI_API_KEY must be injected at runtime (not baked in)

CMD ["python", "runpod_handler.py"]
