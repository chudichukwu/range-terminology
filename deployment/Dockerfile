FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/src backend/src
RUN pip install --no-cache-dir ./backend \
    && useradd --uid 10001 --create-home grandblue \
    && mkdir /data && chown grandblue:grandblue /data
USER grandblue
ENV RANGE_DB_PATH=/data/grandblue.db GRANDBLUE_PRIVATE_BETA=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/health', timeout=4)" || exit 1
CMD ["sh", "-c", "exec uvicorn api.production:create_production_app --factory --host 0.0.0.0 --port \"$PORT\" --workers 1 --proxy-headers"]
