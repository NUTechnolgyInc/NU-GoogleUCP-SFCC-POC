FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY src/business_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install uvicorn

# Copy the source code
COPY src/ /app/src/

# Set Python path to find the business_agent package
ENV PYTHONPATH=/app/src

# Set environment variables (should also be set in Cloud Run console)
ENV PORT=8080

EXPOSE 8080

# Run the application
CMD ["uvicorn", "business_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
