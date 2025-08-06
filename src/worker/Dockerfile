# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

RUN apt update && \
    apt install -y --no-install-recommends \
        curl && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy the requirements file into the container at /app
COPY ./src/worker/requirements.lock /app/requirements.lock

# Install any needed packages specified in requirements.txt
RUN uv pip sync --system --no-cache-dir /app/requirements.lock

# Copy the rest of the application's source code from the context
# The context is the root of the project
COPY ./src /app/src
COPY ./tests /app/tests

# The command to run the application will be specified in docker-compose.yml
