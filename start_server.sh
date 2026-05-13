#!/bin/bash

echo "Nettoyage des processus existants..."
pkill -f "manage.py runserver" 2>/dev/null || true

sleep 3

if lsof -i :8000 >/dev/null 2>&1; then
    echo "Port 8000 encore occupé, tentative de nettoyage forcé..."
    fuser -k 8000/tcp 2>/dev/null || true
    sleep 2
fi

echo "Activation de l'environnement virtuel..."
source .venv/bin/activate

echo "Démarrage du serveur Django..."
python manage.py runserver 0.0.0.0:8000