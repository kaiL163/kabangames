FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/car_puzzles.json backend/party_prompts.json backend/tabletop.py backend/main.py backend/detective.py backend/quiz.py backend/quiz_bank.json backend/car_brands.json backend/writing_game.py backend/party.py backend/spy_game.py backend/reaction.py backend/codenames.py backend/codenames_words.txt backend/codenames_extra.txt backend/codenames_themes.json ./
COPY --from=frontend /build/dist ./static
COPY backend/accounts.py backend/email_verification.py ./
RUN useradd --create-home appuser && mkdir -p /data && chown appuser:appuser /data
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
