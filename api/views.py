"""
API de reconnaissance faciale — BioAttend
==========================================
Endpoint unique : POST /api/face/identify/

Le Raspberry Pi envoie un embedding (vecteur float32, taille 512) extrait
localement par InsightFace. Cette vue compare ce vecteur à ceux stockés en
base de données (pgvector) et retourne l'utilisateur le plus proche si la
distance cosinus est en dessous du seuil défini dans settings.FACE_MATCH_THRESHOLD.

Une authentification légère est requise via:
- Authorization: Bearer <SECRET_KEY>
- X-API-Key: <SECRET_KEY>
"""

import logging
import secrets

from django.conf import settings
from pgvector.django import CosineDistance
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Utilisateur

logger = logging.getLogger(__name__)

EMBEDDING_SIZE = 512 # Config


class FaceIdentifyView(APIView):

    def _extract_api_key(self, request):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        return request.headers.get("X-API-Key", "").strip()

    def _is_authorized(self, request):
        provided_key = self._extract_api_key(request)
        expected_key = getattr(settings, "SECRET_KEY", "")

        if not provided_key or not expected_key:
            return False

        return secrets.compare_digest(provided_key, expected_key)

    def post(self, request):
        if not self._is_authorized(request):
            return Response(
                {
                    "matched": False,
                    "error": "Authentification requise via Authorization Bearer ou X-API-Key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

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

        try:
            embedding = [float(v) for v in embedding_raw]
        except (TypeError, ValueError):
            return Response(
                {"matched": False, "error": "'embedding' doit contenir uniquement des nombres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        threshold = getattr(settings, "FACE_MATCH_THRESHOLD", 0.5)

        try:
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
