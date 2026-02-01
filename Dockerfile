FROM python:3.12-slim

WORKDIR /app

# System deps needed by Playwright's Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl ca-certificates fonts-libcairo libcairo2-dev \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libpangocairo-1.0-0 libasound2 libnspr4 libnss3 \
    libxslt1.1 libenchant-2-2 libhyphen0 libgdk-pixbuf2.0-0 \
    libwoff1 libopenjp2-7 libwebp6 libwebpdemux2 \
    libgudev-1.0-0 libsecret-1-0 libhyphen0 libgdk-pixbuf2.0-0 \
    libegl1 libnotify4 libxslt1.1 libevent-2.1-7 libgles2 \
    libvpx7 libxclip libxsel \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
