FROM python:3.12-slim-trixie
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock && pip check
COPY app.py index.html lighting.js lighting-tools.js govee-cloud.js google-home.js google-home-demo.jpg google-home-show.jpg lighting.css twinkly.svg twinkly-nav-logo.svg hue-app-icon.webp govee-logo.png config.yaml ./
COPY project.html project.css project.js security-center.js CHANGELOG.md ROADMAP.md ./
COPY govee-guide-config.webp govee-guide-yaml.webp govee-guide-cloud.webp ./
COPY effect_previews ./effect_previews
COPY product_photos ./product_photos
COPY images/HUE ./images/HUE
COPY matrix_gifs ./matrix_gifs
RUN python matrix_gifs/generate.py
COPY modules ./modules
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

ENV TWINKLY_HTTP_PORT=18489 TWINKLY_DDP_PORT=18490
