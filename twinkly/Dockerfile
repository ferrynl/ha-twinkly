FROM python:3.12-slim-bookworm
WORKDIR /app
RUN pip install --no-cache-dir aiohttp==3.13.5 xled==0.7.0 Pillow==12.2.0
COPY app.py index.html ./
CMD ["python", "-u", "app.py"]
