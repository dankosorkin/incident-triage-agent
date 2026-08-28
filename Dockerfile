FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml requirements-lock.txt ./
COPY app ./app

RUN pip install --no-cache-dir -r requirements-lock.txt && \
    pip install --no-cache-dir --no-deps .

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
