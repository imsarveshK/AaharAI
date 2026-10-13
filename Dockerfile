FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FOOD_CATALOG_PATH=/app/catalog/data.csv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY android/app/src/commonMain/composeResources/files/aaharai-ifct/data.csv ./catalog/data.csv

RUN useradd --create-home --uid 10001 aaharai && chown -R aaharai:aaharai /app
USER aaharai

EXPOSE 8000

CMD ["uvicorn", "aaharai_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
