"""
Simulation complète — Pipeline InsightFace → API BioAttend
===========================================================
Ce script reproduit exactement ce que fait le Raspberry Pi :
  1. Charge une image de visage réelle (t1.jpg fournie avec insightface)
  2. Extrait l'embedding via InsightFace (modèle buffalo_s)
  3. Enregistre cet embedding dans la base pour un utilisateur de test
  4. Envoie l'embedding à l'API POST /api/face/identify/
  5. Attend "matched: true" → le pipeline est validé de bout en bout

Usage :
    # Terminal 1 — serveur Django
    python manage.py runserver

    # Terminal 2 — simulation
    python simulate_face.py

Prérequis : le serveur Django doit tourner sur localhost:8000
"""

import os
import sys
import warnings
import django
import numpy as np
import cv2
import json
import requests
import insightface
from insightface.app import FaceAnalysis

# Supprime le FutureWarning de scikit-image ≥ 0.26 déclenché par insightface/utils/face_align.py.
# InsightFace 0.7.3 appelle encore tform.estimate() qui est déprécié — ce n'est pas notre code.
warnings.filterwarnings("ignore", category=FutureWarning, module="insightface")

# ── Configuration Django (pour écrire en base) ─────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "BioAttend.settings")
django.setup()

from accounts.models import Utilisateur  # noqa: E402 — après django.setup()

# ── Constantes ──────────────────────────────────────────────────────────────
API_URL = "http://localhost:8000/api/face/identify/"
TEST_IMAGE_PATH = os.path.join(
    os.path.dirname(insightface.__file__),
    "data", "images", "t1.jpg"
)
TEST_USERNAME = "test_simulation"

SEP = "─" * 60


def load_model():
    """Charge le modèle InsightFace (buffalo_s = léger, 512 dims)."""
    print(f"\n{SEP}")
    print("  ÉTAPE 1 — Chargement du modèle InsightFace (buffalo_s)")
    print(SEP)

    app = FaceAnalysis(
        name="buffalo_s",
        allowed_modules=["detection", "recognition"],
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=-1, det_size=(640, 640))
    print("  ✓ Modèle chargé avec succès")
    return app


def extract_embedding(app, image_path):
    """Extrait l'embedding from une image et affiche les infos détectées."""
    print(f"\n{SEP}")
    print("  ÉTAPE 2 — Extraction de l'embedding depuis l'image")
    print(SEP)
    print(f"  Image utilisée : {image_path}")

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image introuvable : {image_path}")

    print(f"  Dimensions image : {img.shape[1]}x{img.shape[0]} px")

    faces = app.get(img)
    if not faces:
        raise RuntimeError("Aucun visage détecté dans l'image de test.")

    face = faces[0]  # prend le visage le plus confiant
    embedding = face.embedding  # np.array float32 shape=(512,)

    print(f"  ✓ Visage détecté — bbox : {face.bbox.astype(int).tolist()}")
    print(f"  ✓ Embedding extrait — taille : {embedding.shape[0]} dimensions")
    print(f"  ✓ Aperçu (5 premières valeurs) : {embedding[:5].tolist()}")

    return embedding


def enroll_user(embedding):
    """Enregistre l'embedding dans la base pour l'utilisateur de test."""
    print(f"\n{SEP}")
    print("  ÉTAPE 3 — Enregistrement de l'embedding en base de données")
    print(SEP)

    user, created = Utilisateur.objects.get_or_create(
        username=TEST_USERNAME,
        defaults={
            "first_name": "Test",
            "last_name": "Simulation",
            "email": "test@bioattend.local",
        },
    )

    user.embedding_facial = embedding.tolist()
    user.save(update_fields=["embedding_facial"])

    action = "créé" if created else "mis à jour"
    print(f"  ✓ Utilisateur '{TEST_USERNAME}' {action} (id: {user.id})")
    return user


def call_api(embedding):
    """Envoie l'embedding à l'API et retourne la réponse."""
    print(f"\n{SEP}")
    print("  ÉTAPE 4 — Appel de l'API POST /api/face/identify/")
    print(SEP)

    payload = {"embedding": embedding.tolist()}
    print(f"  → POST {API_URL}")
    print(f"  → Payload taille : {len(payload['embedding'])} floats")

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
    except requests.exceptions.ConnectionError:
        print("\n  ✗ ERREUR : impossible de joindre le serveur Django.")
        print("    Assure-toi que 'python manage.py runserver' tourne.")
        sys.exit(1)

    print(f"  ← Status HTTP : {response.status_code}")
    return response


def validate(response, expected_username):
    """Vérifie que la réponse API est correcte."""
    print(f"\n{SEP}")
    print("  ÉTAPE 5 — Validation du résultat")
    print(SEP)

    data = response.json()
    print(f"  Réponse JSON :\n{json.dumps(data, indent=4, ensure_ascii=False)}")

    print(f"\n{SEP}")
    if response.status_code == 200 and data.get("matched") is True:
        user_ok = data.get("username") == expected_username
        print(f"  ✓ matched       : True")
        print(f"  {'✓' if user_ok else '✗'} username      : {data.get('username')} (attendu: {expected_username})")
        print(f"  ✓ distance      : {data.get('distance')}")
        print(f"\n  ✅  SIMULATION RÉUSSIE — le pipeline complet fonctionne !")
    else:
        print(f"  ✗ ÉCHEC — réponse inattendue (status {response.status_code})")
        if "error" in data:
            print(f"  Erreur : {data['error']}")
    print(SEP)


def test_wrong_embedding():
    """Test supplémentaire : envoie un embedding aléatoire → doit ≠ match."""
    print(f"\n{SEP}")
    print("  TEST BONUS — Embedding aléatoire (inconnu)")
    print(SEP)

    random_emb = np.random.rand(512).tolist()
    r = requests.post(API_URL, json={"embedding": random_emb}, timeout=10)
    data = r.json()
    print(f"  Status : {r.status_code}")
    print(f"  matched : {data.get('matched')} (attendu : False ou distance élevée)")
    print(f"  → {data}")


# ── Point d'entrée ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'═' * 60}")
    print("  SIMULATION COMPLÈTE — BioAttend Face Identification API")
    print(f"{'═' * 60}")

    app = load_model()
    embedding = extract_embedding(app, TEST_IMAGE_PATH)
    user = enroll_user(embedding)
    response = call_api(embedding)
    validate(response, TEST_USERNAME)
    test_wrong_embedding()

    print()
