FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
# FIX: Entry point was "main:app" but the file is gemini_live.py
CMD ["uvicorn", "gemini_live:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
