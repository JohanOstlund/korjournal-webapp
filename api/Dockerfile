FROM python:3.12-slim

LABEL org.opencontainers.image.title="Korjournal API" \
      org.opencontainers.image.description="Körjournal backend – FastAPI. Default login: admin / admin1234" \
      org.opencontainers.image.source="https://github.com/JohanOstlund/korjournal-webapp"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
