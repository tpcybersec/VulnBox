FROM python:3.11-slim

# Install Chromium runtime dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY PRSSI/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Playwright's Chromium browser binary
RUN playwright install chromium

# Copy app source
COPY PRSSI/app.py .
COPY PRSSI/flag.txt .
COPY PRSSI/static/ ./static/
COPY PRSSI/templates/ ./templates/

# Run with gunicorn for production
EXPOSE 5000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]