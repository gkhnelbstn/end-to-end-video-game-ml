#!/bin/sh
set -e

# Optional: Show Python path
echo "PYTHONPATH: ${PYTHONPATH}"

# Run Alembic migrations if available
echo "Applying database migrations (Alembic) if needed..."
if command -v alembic >/dev/null 2>&1; then
  ATTEMPTS=0
  until [ $ATTEMPTS -ge 5 ]
  do
    if alembic -c /app/src/backend/alembic.ini upgrade head; then
      echo "Alembic migrations applied successfully."
      break
    else
      ATTEMPTS=$((ATTEMPTS+1))
      echo "Alembic upgrade failed (attempt $ATTEMPTS). Retrying in 5s..."
      sleep 5
    fi
  done
else
  echo "Alembic command not found. Skipping migrations."
fi

# Start the FastAPI app
exec uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
