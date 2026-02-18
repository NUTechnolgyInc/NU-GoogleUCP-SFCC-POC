FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY apps/business_agent/src/business_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install uvicorn

# Copy the source code and integration
COPY apps/business_agent/src /app/src
COPY scapi_integration /app/scapi_integration

# Set Python path to find both packages
ENV PYTHONPATH=/app/src:/app

# Set environment variables
ENV PORT=8080

EXPOSE 8080

# Run the application
CMD ["uvicorn", "business_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
