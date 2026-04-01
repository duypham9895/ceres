FROM python:3.11-slim

WORKDIR /app

# Install system deps for Playwright + asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

COPY . .
RUN poetry install --no-interaction --no-ansi

RUN playwright install chromium

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "ceres.api:app", "--host", "0.0.0.0", "--port", "8000"]
