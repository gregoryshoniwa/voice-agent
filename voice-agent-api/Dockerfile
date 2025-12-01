FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Create documents directory
RUN mkdir -p /data/documents

# Copy frontend if it exists
COPY frontend/ /app/frontend/ 2>/dev/null || true

CMD ["python", "app.py"]

