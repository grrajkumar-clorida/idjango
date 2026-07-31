FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=idirect.settings \
    APP_PORT=8008 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# mysqlclient + Chromium for Selenium scrapers (pe_scraper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    chromium \
    chromium-driver \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import django, gunicorn, MySQLdb, selenium; print('deps ok')"

COPY . .

RUN test -f idirect/wsgi.py \
    && test -f idirect/settings.py \
    && test -f manage.py \
    && python -c "import idirect; print('idirect ok')"

RUN if [ -f idirect/.env ]; then python manage.py collectstatic --noinput; fi

EXPOSE 8008

CMD gunicorn idirect.wsgi:application --bind 0.0.0.0:${APP_PORT:-8008} --workers 3 --chdir /app
