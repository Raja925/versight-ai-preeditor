FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend

WORKDIR /app/backend

# Render/Railway inject $PORT at runtime; main.py's __main__ block reads it.
CMD ["python", "main.py"]
