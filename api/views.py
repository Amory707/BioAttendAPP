"""
API de reconnaissance faciale — BioAttend
==========================================
Endpoint unique : POST /api/face/identify/

Le Raspberry Pi envoie un embedding (vecteur float32, taille 512) extrait
localement par InsightFace. Cette vue compare ce vecteur à ceux stockés en
base de données (pgvector) et retourne l'utilisateur le plus proche si la
distance cosinus est en dessous du seuil défini dans settings.FACE_MATCH_THRESHOLD.

Aucune authentification n'est requise sur cet endpoint : il est destiné à
des appareils physiques sur le réseau local.
"""

import logging

from django.conf import settings
from pgvector.django import CosineDistance
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Utilisateur

logger = logging.getLogger(__name__)

# Taille attendue des embeddings InsightFace (buffalo_l / arcface)
EMBEDDING_SIZE = 512


class FaceIdentifyView(APIView):
    """
    Identifie un utilisateur à partir d'un embedding facial.

    Requête attendue
    ----------------
    POST /api/face/identify/
    Content-Type: application/json

    {
        "embedding": [0.123, -0.456, ...]   // liste de 512 floats
    }

    Réponses
    --------
    200 — Utilisateur reconnu
    {
        "matched": true,
        "user_id": "uuid...",
        "username": "jean.dupont",
        "full_name": "Jean Dupont",
        "distance": 0.18
    }

    404 — Aucun utilisateur correspondant trouvé
    {
        "matched": false,
        "error": "Aucun visage correspondant trouvé"
    }

    400 — Requête mal formée (champ manquant, mauvaise taille, etc.)
    {
        "matched": false,
        "error": "..."
    }

    500 — Erreur interne
    {
        "matched": false,
        "error": "Erreur interne du serveur"
    }
    """

    def post(self, request):
        # ── 1. Validation de l'entrée ──────────────────────────────────────
        embedding_raw = request.data.get("embedding")

        if embedding_raw is None:
            return Response(
                {"matched": False, "error": "Le champ 'embedding' est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(embedding_raw, list):
            return Response(
                {"matched": False, "error": "'embedding' doit être une liste de floats."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(embedding_raw) != EMBEDDING_SIZE:
            return Response(
                {
                    "matched": False,
                    "error": (
                        f"L'embedding doit avoir exactement {EMBEDDING_SIZE} dimensions, "
                        f"{len(embedding_raw)} reçues."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vérification que tous les éléments sont bien numériques
        try:
            embedding = [float(v) for v in embedding_raw]
        except (TypeError, ValueError):
            return Response(
                {"matched": False, "error": "'embedding' doit contenir uniquement des nombres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 2. Recherche de la correspondance via pgvector ─────────────────
        threshold = getattr(settings, "FACE_MATCH_THRESHOLD", 0.5)

        try:
            # CosineDistance retourne une valeur entre 0 (identique) et 2 (opposé).
            # On ne considère que les utilisateurs qui ont un embedding enregistré.
            match = (
                Utilisateur.objects.filter(embedding_facial__isnull=False)
                .annotate(distance=CosineDistance("embedding_facial", embedding))
                .order_by("distance")
                .first()
            )
        except Exception:
            logger.exception("Erreur lors de la requête pgvector dans FaceIdentifyView")
            return Response(
                {"matched": False, "error": "Erreur interne du serveur."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ── 3. Décision : match ou non ─────────────────────────────────────
        if match is None or match.distance > threshold:
            logger.info(
                "Aucune correspondance faciale (meilleure distance : %s)",
                getattr(match, "distance", "N/A"),
            )
            return Response(
                {"matched": False, "error": "Aucun visage correspondant trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info(
            "Visage reconnu : %s (distance cosinus : %.4f)",
            match.username,
            match.distance,
        )

        return Response(
            {
                "matched": True,
                "user_id": str(match.id),
                "username": match.username,
                "full_name": match.get_full_name(),
                "distance": round(float(match.distance), 6),
            },
            status=status.HTTP_200_OK,
        )
