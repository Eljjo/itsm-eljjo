# Two rules from API.md section 9: install every dependency at BUILD time (the grader's sandbox has no
# network once the image is built) and listen on port 8080 inside the container.
FROM python:3.13-slim

WORKDIR /app

# Dependencies first, so Docker caches this layer while editing code.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

# The SQLite file goes to /data (a named volume in docker-compose.yml), so tickets survive a restart.
RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --retries=20 --start-period=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
