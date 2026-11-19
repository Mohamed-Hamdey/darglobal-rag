# --- Builder Stage ---
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY app ./app
COPY index ./index

# --- Runtime Stage ---
FROM python:3.11-slim
RUN useradd -m app
WORKDIR /srv
COPY --from=builder /install /usr/local
COPY app ./app
COPY index ./index

USER app
ENV PORT=8000 PYTHONUNBUFFERED=1

HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]