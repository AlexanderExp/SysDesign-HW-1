FROM python:3.11-slim
WORKDIR /app
COPY services/billing-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/billing-worker /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
CMD ["python", "main.py"]
