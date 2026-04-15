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
from django.db import transaction
from django.utils import timezone
from pgvector.django import CosineDistance
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Utilisateur
from attendance.models import Pointage

logger = logging.getLogger(__name__)

EMBEDDING_SIZE = 512 # Config


class DeviceApiAuthMixin:
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


class FaceIdentifyView(DeviceApiAuthMixin, APIView):

    @staticmethod
    def _score_confiance_from_distance(distance):
        try:
            value = 1.0 - float(distance)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _next_pointage_type_for_pointeuse(utilisateur):
        last_pointage = (
            Pointage.objects.select_for_update()
            .filter(utilisateur=utilisateur, origine=Pointage.ORIGINE_POINTEUSE)
            .order_by("-horodatage", "-id")
            .first()
        )

        if last_pointage is None or last_pointage.type == "SORTIE":
            return "ENTREE"
        return "SORTIE"

    @staticmethod
    def _create_incident_pointage(incident_type, description, score_confiance=0.0, utilisateur=None, details=None, device_name=''):
        if details is None:
            details = {}

        Pointage.objects.create(
            utilisateur=utilisateur,
            statut='NON_VALIDE',
            horodatage=timezone.now(),
            type='ENTREE',
            score_confiance=score_confiance,
            origine=Pointage.ORIGINE_POINTEUSE,
            incident_type=incident_type,
            device_name=device_name,
            details=details,
        )

    @classmethod
    def _create_unknown_user_event(cls, best_distance=None):
        if best_distance is None:
            description = "Tentative de pointage avec un visage non reconnu (aucune correspondance)."
        else:
            description = (
                "Tentative de pointage avec un visage non reconnu "
                f"(meilleure distance={best_distance:.4f})."
            )

        cls._create_incident_pointage(
            incident_type='UTILISATEUR_INCONNU',
            description=description,
            score_confiance=0.0,
            details={'best_distance': best_distance},
        )

    @classmethod
    def _create_recognition_failure_event(cls, utilisateur, distance):
        username = getattr(utilisateur, "username", "inconnu")
        utilisateur_associe = utilisateur if isinstance(utilisateur, Utilisateur) else None
        description = (
            "Tentative de pointage en echec de reconnaissance "
            f"(utilisateur candidat={username}, distance={distance:.4f})."
        )
        cls._create_incident_pointage(
            incident_type='ECHEC_RECONNAISSANCE',
            description=description,
            score_confiance=cls._score_confiance_from_distance(distance),
            utilisateur=utilisateur_associe,
            details={'candidate_username': username, 'distance': float(distance)},
        )

    @classmethod
    def _create_fraud_event(cls, reason="Tentative de fraude detectee (photo imprimee, video ou autre)."):
        cls._create_incident_pointage(
            incident_type='TENTATIVE_FRAUDE',
            description=reason,
            score_confiance=0.0,
        )

    def post(self, request):
        if not self._is_authorized(request):
            return Response(
                {
                    "matched": False,
                    "error": "Authentification requise via Authorization Bearer ou X-API-Key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        fraud_detected = request.data.get("fraud_detected", False)
        fraud_reason = request.data.get("fraud_reason", "Tentative de fraude detectee (photo imprimee, video ou autre).")
        if fraud_detected:
            logger.warning("Tentative de fraude signalee par la pointeuse: %s", fraud_reason)
            self._create_fraud_event(fraud_reason)
            return Response(
                {"matched": False, "error": "Tentative de fraude detectee."},
                status=status.HTTP_403_FORBIDDEN,
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

        if match is None:
            logger.info(
                "Aucune correspondance faciale (meilleure distance : %s)",
                getattr(match, "distance", "N/A"),
            )
            self._create_unknown_user_event(getattr(match, "distance", None))
            return Response(
                {"matched": False, "error": "Aucun visage correspondant trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if match.distance > threshold:
            logger.info(
                "Correspondance rejetee (utilisateur=%s, distance=%.4f, seuil=%.4f)",
                getattr(match, "username", "inconnu"),
                match.distance,
                threshold,
            )
            self._create_recognition_failure_event(match, match.distance)
            return Response(
                {"matched": False, "error": "Aucun visage correspondant trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info(
            "Visage reconnu : %s (distance cosinus : %.4f)",
            match.username,
            match.distance,
        )

        with transaction.atomic():
            pointage_type = self._next_pointage_type_for_pointeuse(match)
            pointage = Pointage.objects.create(
                utilisateur=match,
                statut="VALIDE",
                horodatage=timezone.now(),
                type=pointage_type,
                score_confiance=self._score_confiance_from_distance(match.distance),
                origine=Pointage.ORIGINE_POINTEUSE,
            )

        return Response(
            {
                "matched": True,
                "user_id": str(match.id),
                "username": match.username,
                "full_name": match.get_full_name(),
                "distance": round(float(match.distance), 6),
                "pointage_id": str(pointage.id),
                "pointage_type": pointage.type,
            },
            status=status.HTTP_200_OK,
        )


class FrontEventView(DeviceApiAuthMixin, APIView):
    EVENT_TYPE_MAP = {
        "unknown_user": "UTILISATEUR_INCONNU",
        "recognition_failed": "ECHEC_RECONNAISSANCE",
        "spoof_attempt": "TENTATIVE_FRAUDE",
    }
    EVENT_STATUS_MAP = {
        "error": "ERROR",
        "rejected": "REJECTED",
        "blocked": "BLOCKED",
    }

    def post(self, request):
        if not self._is_authorized(request):
            return Response(
                {
                    "logged": False,
                    "error": "Authentification requise via Authorization Bearer ou X-API-Key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        event_type = request.data.get("event_type")
        event_status = request.data.get("status")
        message = request.data.get("message")
        device_name = request.data.get("device_name")
        details = request.data.get("details", {})

        if event_type not in self.EVENT_TYPE_MAP:
            return Response(
                {
                    "logged": False,
                    "error": "'event_type' doit être l'une des valeurs: unknown_user, recognition_failed, spoof_attempt.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event_status not in self.EVENT_STATUS_MAP:
            return Response(
                {
                    "logged": False,
                    "error": "'status' doit être l'une des valeurs: error, rejected, blocked.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(message, str) or not message.strip():
            return Response(
                {
                    "logged": False,
                    "error": "Le champ 'message' est requis et doit être une chaine non vide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(device_name, str) or not device_name.strip():
            return Response(
                {
                    "logged": False,
                    "error": "Le champ 'device_name' est requis et doit être une chaine non vide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(details, dict):
            return Response(
                {
                    "logged": False,
                    "error": "Le champ 'details' doit être un objet JSON.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pointage = Pointage.objects.create(
            utilisateur=None,
            statut='NON_VALIDE',
            horodatage=timezone.now(),
            type='ENTREE',
            score_confiance=0.0,
            origine=Pointage.ORIGINE_POINTEUSE,
            incident_type=self.EVENT_TYPE_MAP[event_type],
            device_name=device_name.strip(),
            details={
                'status': self.EVENT_STATUS_MAP[event_status],
                **details,
            },
        )

        logger.info(
            "Evenement borne journalise: type=%s status=%s device=%s pointage_id=%s",
            event_type,
            event_status,
            device_name,
            pointage.id,
        )

        return Response(
            {
                "logged": True,
                "event_id": str(pointage.id),
                "event_type": event_type,
                "status": event_status,
            },
            status=status.HTTP_201_CREATED,
        )
