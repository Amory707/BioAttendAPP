# Depuis votre serveur root@Bioattend
cd /tmp
rm -rf BioAttendAPP  # Nettoyage
git clone git@github.com:Nde-Code/BioAttendAPP.git
cd BioAttendAPP

# Vérifier le contenu actuel du Dockerfile (s'il existe)
cat Dockerfile

# Supprimer et recréer proprement
rm -f Dockerfile

# Créer le Dockerfile avec le bon contenu
cat > Dockerfile << 'DOCKERFILEEND'
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Installer les dépendances système nécessaires pour compiler les packages Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Créer un environnement virtuel
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copier requirements et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn==21.2.0

# Stage 2: Runtime stage
FROM python:3.11-slim

# Installer seulement les dépendances runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copier l'environnement virtuel depuis le builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Créer un utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 bioattend && \
    mkdir -p /app /app/staticfiles /app/media && \
    chown -R bioattend:bioattend /app

# Définir le répertoire de travail
WORKDIR /app

# Copier le code de l'application
COPY --chown=bioattend:bioattend . .

# Exposer le port
EXPOSE 80

# Utiliser l'utilisateur non-root
USER bioattend

# Script de démarrage
CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    gunicorn BioAttend.wsgi:application \
    --bind 0.0.0.0:80 \
    --workers 4 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
DOCKERFILEEND

# Vérifier que le fichier est correct
echo "=== Contenu du Dockerfile ==="
cat Dockerfile
echo "==========================="

# Vérifier qu'il n'y a pas de caractères bizarres
file Dockerfile

# Commiter et pusher
git add Dockerfile
git commit -m "Fix Dockerfile with correct syntax"
git push origin main
