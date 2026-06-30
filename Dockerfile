FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for bcrypt
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

# Default environment variables (override in docker-compose or CasaOS)
ENV SQLALCHEMY_DATABASE_URI="sqlite:////app/data/dashboard.db"
ENV SECRET_KEY="super-secret-key-change-me-in-production"
ENV ALLOWED_ORIGINS="*"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
