FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY . .

RUN playwright install chromium

EXPOSE 8000
CMD ["uvicorn", "ceres.api:app", "--host", "0.0.0.0", "--port", "8000"]
