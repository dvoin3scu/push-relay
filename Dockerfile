FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUSH_PORT=8099 \
    PUSH_CONFIG_DIR=/config

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --system --uid 99 --gid 100 --no-create-home push \
 && mkdir -p /config && chown 99:100 /config

COPY push_relay ./push_relay

USER 99:100
EXPOSE 8099
VOLUME /config

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PUSH_PORT\",\"8099\")}/health', timeout=4)"

CMD ["python", "-m", "push_relay"]
