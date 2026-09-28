FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 U2NET_HOME=/models
RUN apt-get update && apt-get install -y --no-install-recommends curl libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd -m -u 1000 app && mkdir -p /models && chown app:app /models
USER app
COPY --chown=app:app app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
