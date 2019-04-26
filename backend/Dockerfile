FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# collectstatic only needs settings to import; no database connection is made.
RUN DJANGO_SECRET_KEY=build-only DATABASE_URL=postgres://build@localhost/build python manage.py collectstatic --noinput

RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
ENV ENCODE_TOKEN=true
ENV CHECK_STATUS=true