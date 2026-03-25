"""
Script de test de l'API /api/face/identify/
-------------------------------------------
Simule ce que ferait le Raspberry Pi.

Usage :
    python test_api.py

Le serveur Django doit tourner : python manage.py runserver
"""

import json
import random

import requests

BASE_URL = "http://localhost:8000/api/face/identify/"
EMBEDDING_SIZE = 512


def random_embedding():
    """Génère un vecteur aléatoire de 512 floats (comme InsightFace le ferait)."""
    return [random.uniform(-1.0, 1.0) for _ in range(EMBEDDING_SIZE)]


def test_valid_request():
    print("\n── Test 1 : requête valide (embedding 512 floats) ──")
    payload = {"embedding": random_embedding()}
    r = requests.post(BASE_URL, json=payload)
    print(f"  Status  : {r.status_code}")
    print(f"  Réponse : {json.dumps(r.json(), indent=4, ensure_ascii=False)}")


def test_missing_embedding():
    print("\n── Test 2 : champ 'embedding' manquant ──")
    r = requests.post(BASE_URL, json={})
    print(f"  Status  : {r.status_code}")  # attendu : 400
    print(f"  Réponse : {r.json()}")


def test_wrong_size():
    print("\n── Test 3 : mauvaise taille (100 floats au lieu de 512) ──")
    payload = {"embedding": random_embedding()[:100]}
    r = requests.post(BASE_URL, json=payload)
    print(f"  Status  : {r.status_code}")  # attendu : 400
    print(f"  Réponse : {r.json()}")


def test_invalid_values():
    print("\n── Test 4 : valeurs non numériques ──")
    bad = ["abc"] * EMBEDDING_SIZE
    r = requests.post(BASE_URL, json={"embedding": bad})
    print(f"  Status  : {r.status_code}")  # attendu : 400
    print(f"  Réponse : {r.json()}")


if __name__ == "__main__":
    print("=== Tests API BioAttend — POST /api/face/identify/ ===")
    test_valid_request()
    test_missing_embedding()
    test_wrong_size()
    test_invalid_values()
    print("\n=== Fin des tests ===")
