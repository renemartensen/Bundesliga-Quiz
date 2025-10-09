# Basisimage mit Python
FROM python:3.12-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# requirements installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code kopieren
COPY . .

# Standardbefehl (Scraper starten)
CMD ["python", "scraping.py"]