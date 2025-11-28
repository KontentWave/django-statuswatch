FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential wget && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=app.settings
ENV PORT=8000
# ensure logs dir exists for build-time logging
RUN mkdir -p /app/logs && \
    DEBUG=True SECRET_KEY="build-temp" DJANGO_ENV=build \
    python manage.py collectstatic --noinput
CMD ["gunicorn","app.wsgi:application","--bind","0.0.0.0:8000","--workers","3","--timeout","120"]
