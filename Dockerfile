# --- Runtime Stage ---
FROM python:3.11-slim

# Create a non-root user for security
RUN useradd -m app
WORKDIR /srv

# Install runtime dependencies only
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and the pre-built SQLite index
COPY app ./app
COPY index ./index

# Copy runtime data files (gazetteer and cached starter answers)
COPY data/gazetteer.json ./data/gazetteer.json
COPY data/starter_answers.json ./data/starter_answers.json

# Switch to non-root user
USER app
ENV PORT=8000 PYTHONUNBUFFERED=1

# Health check for Render
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# Run with 1 worker to strictly respect the 512MB RAM limit
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]