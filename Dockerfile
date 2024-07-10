# Use an official Python image from Docker Hub with a specific version tag
FROM python:3.9

# Set environment variable to ensure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# Install necessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    netcat-openbsd \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create the working directory
WORKDIR /app

# Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools

# Copy and install Python package requirements
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . /app

# Expose the port
EXPOSE 5000

# Make the start script executable
RUN chmod +x /app/start.sh

# Set the entrypoint
ENTRYPOINT ["/app/start.sh"]
