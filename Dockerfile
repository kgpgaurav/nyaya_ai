FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN useradd --create-home --uid 10001 nyaya
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY alembic.ini .
COPY migrations migrations
COPY app app
COPY scripts scripts
COPY tests tests
COPY pytest.ini .

FROM base AS dev
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
USER nyaya

FROM base AS runtime
USER nyaya
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
