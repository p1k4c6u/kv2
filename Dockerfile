FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers + all system deps (handles distro differences automatically)
RUN playwright install-deps chromium && playwright install chromium

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
