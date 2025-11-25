# -------- Build assets (Tailwind) --------
FROM node:20-alpine AS assets
WORKDIR /app
COPY package*.json tailwind.config.js postcss.config.js ./
COPY src ./src
RUN npm ci
RUN npm run build:css

# -------- Final Python image (prod) --------
FROM python:3.11-slim AS prod
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# -------- System dependencies --------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Pre-creates the folders used by the app (even though the /app/data volume will replace them)
RUN mkdir -p /app/data/uploads /app/static/css

# -------- Pythons Libs Used --------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------- Application code (Code + templates + static then we overwrite/add the generated CSS) --------
COPY . .

# -------- Expose API port --------
EXPOSE 9010

# Uvicorn simple: in real production you can switch to Gunicorn + Uvicorn Worker
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "9010"]