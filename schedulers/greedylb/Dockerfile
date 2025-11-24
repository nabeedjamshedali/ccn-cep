FROM python:3.11-slim

LABEL maintainer="Adaptive Load Balancing Team"
LABEL description="GreedyLB Scheduler - Fast scheduling for stable workloads"

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scheduler code
COPY scheduler.py .

# Make scheduler executable
RUN chmod +x scheduler.py

# Run as non-root user for security
RUN useradd -m -u 1000 scheduler && chown -R scheduler:scheduler /app
USER scheduler

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# Run the scheduler
CMD ["python", "-u", "scheduler.py"]
