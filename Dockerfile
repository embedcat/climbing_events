# Use an official Python runtime as a parent image
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libwebp-dev \
    libpng-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml uv.lock /app/
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy project
COPY . /app/

# Expose port 8000
EXPOSE 8000

# Set entrypoint using python to avoid shell/line-ending issues
ENTRYPOINT ["python", "/app/entrypoint.py"]

# Default command
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
