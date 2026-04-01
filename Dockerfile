FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

COPY . .
RUN poetry install --no-interaction --no-ansi

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "ceres.api:app", "--host", "0.0.0.0", "--port", "8000"]
