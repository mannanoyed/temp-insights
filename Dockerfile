# =========================================
# meet-insights — CPU-only FastAPI service
# Gemini-based meeting analysis
# Will be replaced by IRIS agent in a future iteration
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
COPY main.py .

# Runtime env
ENV PYTHONUNBUFFERED=1
# GEMINI_API_KEY must be injected at runtime (not baked in)

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
