# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install required system packages
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv pip wrapper
RUN pip install --no-cache-dir uv

# Copy and install Python dependencies
COPY ./src/backend/requirements.txt /app/
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy application source code
COPY ./src /app/src
COPY ./tests /app/tests

# Set default command for backend
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
