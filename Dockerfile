# Use an official Python image from Docker Hub with a specific version tag
FROM python:3.9
# Set environment variable to ensure Python output is unbuffered
ENV PYTHONUNBUFFERED 1

# Install necessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev\
    libffi-dev \
    libssl-dev \
    netcat-openbsd \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create the working directory
RUN mkdir /app
WORKDIR /app

# Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools

# Copy and install Python package requirements
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app

EXPOSE 5000
RUN chmod +x /app/start.sh

ENTRYPOINT ["./start.sh"]
