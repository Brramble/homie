# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create directory for SQLite database
RUN mkdir -p /app/data

# Expose port 5000
EXPOSE 5000

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Create entrypoint script to handle permissions
RUN echo '#!/bin/bash\n\
# Ensure database file has correct permissions if it exists\n\
if [ -f /app/homie.db ]; then\n\
    chown appuser:appuser /app/homie.db\n\
    chmod 664 /app/homie.db\n\
fi\n\
# Ensure data directory has correct permissions\n\
mkdir -p /app/data\n\
chown -R appuser:appuser /app/data\n\
# Switch to non-root user and run the app\n\
exec su appuser -c "python /app/app.py"' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Run the application via entrypoint script
CMD ["/entrypoint.sh"]