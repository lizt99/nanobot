FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install Agent API dependencies
COPY nanobot/agent_platform/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Nanobot Library Source (for utils like bip340)
COPY nanobot/ /app/nanobot/
# Add /app to PYTHONPATH so "import nanobot" works
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Copy Agent API Application Code
COPY nanobot/agent_platform/app /app/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["/usr/local/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
