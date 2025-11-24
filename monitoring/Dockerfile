FROM python:3.11-slim

LABEL maintainer="Adaptive Load Balancing Team"
LABEL description="Pattern Detector - Monitors workload patterns and switches schedulers"

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy monitoring code
COPY pattern_detector.py .

# Make script executable
RUN chmod +x pattern_detector.py

# Run as non-root user for security
RUN useradd -m -u 1000 monitor && chown -R monitor:monitor /app
USER monitor

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# Run the pattern detector
CMD ["python", "-u", "pattern_detector.py"]
