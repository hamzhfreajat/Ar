FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Not root inside the container
RUN useradd --create-home --uid 10001 kitabcom
USER kitabcom

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/v1/health', timeout=4)"

# The port is written out, not read from a variable: a platform may set PORT to something else.
# One worker: two would race to create the tables on the first start.
# Behind Coolify's proxy its forwarded headers are trusted, so request URLs come out as https.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--proxy-headers", "--forwarded-allow-ips", "*"]
