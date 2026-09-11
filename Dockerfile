FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends bash && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

WORKDIR /app

# Copy pyproject.toml and uv.lock
COPY pyproject.toml uv.lock ./

# Install dependencies into the system environment
RUN uv sync --system

# Copy application source code
COPY . .

# Ensure start.sh is executable
RUN chmod +x ./start.sh

# Expose FastMCP ports
EXPOSE 8001 8002 8003

# Run the startup script
CMD ["./start.sh"]
