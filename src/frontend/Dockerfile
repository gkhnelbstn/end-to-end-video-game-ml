# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install uv
RUN pip install uv

# Copy the requirements file into the container at /app
COPY ./src/frontend/requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN uv pip install --system --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application's source code from the context
COPY ./src/frontend /app/src/frontend

# Run the Streamlit app
CMD ["streamlit", "run", "src/frontend/app.py"]
