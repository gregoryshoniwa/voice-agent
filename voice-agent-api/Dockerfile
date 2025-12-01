FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Create documents directory
RUN mkdir -p /data/documents

# Create frontend directory (will be mounted as volume at runtime)
RUN mkdir -p /app/frontend

CMD ["python", "app.py"]

