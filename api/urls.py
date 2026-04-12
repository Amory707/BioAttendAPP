"""
URLs de l'app api — BioAttend
==============================
Préfixe : /api/  (défini dans BioAttend/urls.py)

Endpoints disponibles
---------------------
POST /api/face/identify/  → FaceIdentifyView
    Reçoit un embedding (512 floats) et retourne l'utilisateur reconnu.
"""

from django.urls import path

from .views import FaceIdentifyView, FrontEventView

app_name = "api"

urlpatterns = [
    path("face/identify/", FaceIdentifyView.as_view(), name="face-identify"),
    path("front/events/", FrontEventView.as_view(), name="front-events"),
]
