# 1. Utiliser une image Python légère
FROM python:3.10-slim

# 2. Définir le répertoire de travail
WORKDIR /app

# 3. Installer les dépendances système (nécessaires pour psycopg2 et l'audio)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 4. Créer un utilisateur non-root (sécurité exigée par Hugging Face)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# 5. Copier et installer les dépendances Python
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 6. Copier tout le reste du code
COPY --chown=user . .

# 7. Exposer le port 7860 (Port par défaut de Hugging Face Spaces)
EXPOSE 7860

# 8. Lancer l'application avec Uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]