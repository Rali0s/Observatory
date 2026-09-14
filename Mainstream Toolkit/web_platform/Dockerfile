FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/web_platform
COPY web_platform/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY narrative_engine.py semantic_engine.py publisher.py analysis_engine.py openai_notes.py /app/
COPY web_platform/ ./
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput
RUN useradd --create-home observatory && chown -R observatory:observatory /app
USER observatory
CMD ["sh", "-c", "gunicorn observatory.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile -"]
