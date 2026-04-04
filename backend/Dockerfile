FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

ENV PYTHONPATH=/srv

EXPOSE 8000

CMD ["uvicorn", "app.main:server", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
