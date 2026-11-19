FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock && pip check
COPY app.py index.html lighting.js lighting.css twinkly.svg twinkly-nav-logo.svg hue-app-icon.webp govee-logo.png config.yaml ./
COPY effect_previews ./effect_previews
COPY product_photos ./product_photos
COPY matrix_gifs ./matrix_gifs
RUN python matrix_gifs/generate.py
COPY modules ./modules
COPY test_*.py ./
RUN python -m py_compile app.py test_dashboard.py && python -m unittest discover -v
CMD ["python", "-u", "app.py"]

ENV TWINKLY_HTTP_PORT=18491 TWINKLY_DDP_PORT=18492
