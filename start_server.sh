#!/bin/bash
# Script de démarrage propre pour BioAttend

echo "🧹 Nettoyage des processus existants..."
# Tuer tous les serveurs Django existants
pkill -f "manage.py runserver" 2>/dev/null || true

# Attendre que les processus se terminent
sleep 3

# Vérifier si le port est encore occupé
if lsof -i :8000 >/dev/null 2>&1; then
    echo "❌ Port 8000 encore occupé, tentative de nettoyage forcé..."
    fuser -k 8000/tcp 2>/dev/null || true
    sleep 2
fi

echo "🔧 Activation de l'environnement virtuel..."
source .venv/bin/activate

echo "🚀 Démarrage du serveur Django..."
python manage.py runserver 0.0.0.0:8000