#!/bin/bash
set -e

echo "Waiting for database to be ready..."
# Wait for the database to be ready
until pg_isready -h database -p 5432 -U stockuser; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

echo "Database is ready!"

echo "Running Alembic migrations..."
# Run database migrations
alembic upgrade head

echo "Starting application..."
# Start the FastAPI application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
