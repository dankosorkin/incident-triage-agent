FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml requirements-lock.txt ./
COPY app ./app

RUN pip install --no-cache-dir -r requirements-lock.txt && \
    pip install --no-cache-dir --no-deps .

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Run as a non-root user -- if a dependency vulnerability is ever
# exploited, root inside the container is one less privilege an
# attacker gets for free. Create /app/data and hand it to appuser
# before the volume mount takes over that path: on first use, Docker
# initializes a named volume from the image directory's contents *and
# ownership*, so this is what makes the mounted volume writable by a
# non-root process later, not just this build step.
RUN useradd --create-home --uid 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
