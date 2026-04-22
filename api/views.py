"""
API de reconnaissance faciale — BioAttend
==========================================
Endpoints principaux :
- POST /api/face/identify/ : identification faciale depuis la pointeuse
- POST /api/schedule/absence-alert/ : déclenche la détection d'absence et l'envoi de mail si la journée de l'employé est terminée

Le Raspberry Pi envoie un embedding (vecteur float32, taille 512) extrait
localement par InsightFace. Cette vue compare ce vecteur à ceux stockés en
base de données (pgvector) et retourne l'utilisateur le plus proche si la
distance cosinus est en dessous du seuil défini dans settings.FACE_MATCH_THRESHOLD.

Une authentification légère est requise via:
- Authorization: Bearer <SECRET_KEY>
- X-API-Key: <SECRET_KEY>
"""

import datetime
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
from alerts.models import Alerte
from attendance.models import Pointage
from schedule.services import (
    build_pointage_feedback,
    trigger_absence_alerts_for_day,
)

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
    INGESTION_MODE_PRODUCTION = "production"
    INGESTION_MODE_TEST = "test"

    @classmethod
    def _resolve_ingestion_mode(cls, request):
        mode = request.data.get("ingestion_mode", cls.INGESTION_MODE_PRODUCTION)
        if not isinstance(mode, str):
            return None
        normalized = mode.strip().lower()
        if normalized in {cls.INGESTION_MODE_PRODUCTION, cls.INGESTION_MODE_TEST}:
            return normalized
        return None

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

        incident_details = {
            **details,
            'message': description,
        }

        pointage = Pointage.objects.create(
            utilisateur=utilisateur,
            statut='NON_VALIDE',
            horodatage=timezone.now(),
            type='ENTREE',
            score_confiance=score_confiance,
            origine=Pointage.ORIGINE_POINTEUSE,
            incident_type=incident_type,
            device_name=device_name,
            details=incident_details,
        )

        Alerte.create_or_update_for_incident(
            incident_type,
            description,
            pointage=pointage,
            utilisateur=utilisateur,
            device_name=device_name,
            details=incident_details,
        )
        return pointage

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

        ingestion_mode = self._resolve_ingestion_mode(request)
        if ingestion_mode is None:
            return Response(
                {
                    "matched": False,
                    "error": "Le champ 'ingestion_mode' doit être 'production' ou 'test'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_test_mode = ingestion_mode == self.INGESTION_MODE_TEST

        fraud_detected = request.data.get("fraud_detected", False)
        fraud_reason = request.data.get("fraud_reason", "Tentative de fraude detectee (photo imprimee, video ou autre).")
        if fraud_detected:
            logger.warning("Tentative de fraude signalee par la pointeuse: %s", fraud_reason)
            if not is_test_mode:
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
            if not is_test_mode:
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
            if not is_test_mode:
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

        pointage = None
        punctuality_feedback = {"messages": [], "flags": [], "worked_duration_display": "0h00"}
        if not is_test_mode:
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

            punctuality_feedback = build_pointage_feedback(pointage)

        return Response(
            {
                "matched": True,
                "user_id": str(match.id),
                "username": match.username,
                "full_name": match.get_full_name(),
                "distance": round(float(match.distance), 6),
                "pointage_id": str(pointage.id) if pointage else None,
                "pointage_type": pointage.type if pointage else None,
                "schedule_feedback": punctuality_feedback.get("messages", []),
                "schedule_flags": punctuality_feedback.get("flags", []),
                "worked_duration_display": punctuality_feedback.get("worked_duration_display", "0h00"),
                "ingestion_mode": ingestion_mode,
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
                'message': message.strip(),
                **details,
            },
        )

        Alerte.create_or_update_for_incident(
            self.EVENT_TYPE_MAP[event_type],
            message.strip(),
            pointage=pointage,
            event_status=self.EVENT_STATUS_MAP[event_status],
            device_name=device_name.strip(),
            details=pointage.details,
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


class AbsenceAlertView(DeviceApiAuthMixin, APIView):
    def _parse_date(self, date_string):
        if date_string is None:
            return timezone.localdate(), None

        if not isinstance(date_string, str):
            return None, Response(
                {
                    "alert_sent": False,
                    "error": "Le paramètre 'date' doit être une chaîne au format YYYY-MM-DD.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            return datetime.strptime(date_string, "%Y-%m-%d").date(), None
        except ValueError:
            return None, Response(
                {
                    "alert_sent": False,
                    "error": "Le paramètre 'date' doit être au format YYYY-MM-DD.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _handle_request(self, target_day):
        result = trigger_absence_alerts_for_day(target_day)
        return Response(
            {
                "checked": result["checked"],
                "date": result["date"].strftime("%Y-%m-%d"),
                "absences": result["absences"],
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        
        if not self._is_authorized(request):
            return Response(
                {
                    "alert_sent": False,
                    "error": "Authentification requise via Authorization Bearer ou X-API-Key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        target_day, error = self._parse_date(request.query_params.get("date"))
        if error is not None:
            return error

        return self._handle_request(target_day)

    def post(self, request):
        if not self._is_authorized(request):
            return Response(
                {
                    "alert_sent": False,
                    "error": "Authentification requise via Authorization Bearer ou X-API-Key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        target_day, error = self._parse_date(request.data.get("date"))
        if error is not None:
            return error

        return self._handle_request(target_day)
