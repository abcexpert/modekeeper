FROM python:3.12-slim

WORKDIR /app
COPY src/modekeeper /app/modekeeper

ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "modekeeper.trainer"]
