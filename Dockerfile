FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run the application
CMD sh -c 'mkdir -p .streamlit && echo "$SECRETS_TOML" > .streamlit/secrets.toml && streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0'
