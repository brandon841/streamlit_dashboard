# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY utilities.py .
COPY df_explanation.md .

# Note: .env file not copied - use Cloud Run environment variables instead

# Expose port (Cloud Run will set PORT env variable)
ENV PORT=8080
EXPOSE 8080

# Create .streamlit directory for config
RUN mkdir -p /root/.streamlit

# Configure Streamlit for Cloud Run
RUN echo "\
[server]\n\
headless = true\n\
port = 8080\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
address = 0.0.0.0\n\
\n\
[browser]\n\
gatherUsageStats = false\n\
" > /root/.streamlit/config.toml

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health || exit 1

# Run the application
CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
