FROM python:3.12-slim-trixie
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock && pip check
COPY app.py index.html twinkly.svg twinkly-wordmark.svg ./
COPY matrix_gifs ./matrix_gifs
RUN python matrix_gifs/generate.py
COPY test_*.py ./
RUN python -m py_compile app.py test_dashboard.py && python -m unittest discover -v
# The Supervisor mounts /data over the image filesystem, with existing files
# owned by root. The entrypoint fixes their ownership before starting the app.
RUN groupadd --gid 10001 twinkly \
    && useradd --uid 10001 --gid twinkly --home-dir /data --no-create-home --no-log-init twinkly
COPY run.sh ./
ENTRYPOINT ["/bin/sh", "/app/run.sh"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('TWINKLY_HTTP_PORT', '18489') + '/healthz', timeout=3).close()"]
CMD ["python", "-u", "/app/app.py"]
