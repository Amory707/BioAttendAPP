# 🧬 BioAttend

BioAttend est la plateforme de gestion des pointages biométriques (reconnaissance faciale) et de planning. Ce README centralise :

- Présentation du projet
- Démarrage rapide (local / Docker)
- Dépendances
- Dockerfile et notes de déploiement
- Documentation complète des endpoints API (/api/)
- Liste des routes web (UI) exposées par les apps
- Structure du dépôt et explication des composants
- Exemples d'utilisation (cURL)
- Tests, conseils de développement et dépannage

---

## Sommaire

- Présentation
- Quickstart
  - Prérequis
  - Lancer en Docker
  - Lancer localement (venv)
- Variables d'environnement principales
- Dockerfile (extrait)
- Dépendances
- API — Documentation complète
  - POST /api/face/identify/
  - POST /api/front/events/
  - GET, POST /api/schedule/absence-alert/
- Routes web / UI (liste)
- Structure de fichiers (arborescence)
- Tests & quality
- Développement & bonnes pratiques
- Déploiement & opération
- FAQ & dépannage
- Contribuer
- Licence

---

## Présentation

BioAttend fournit :
- Pointage via reconnaissance faciale (pointeuses / Raspberry Pi + InsightFace).
- Gestion des employés, alertes et plannings.
- Interface web d'administration et tableau de bord.
- API rest légère protégée par clé (Authorization Bearer | X-API-Key).

Langages dominants : Python (Django & DRF), HTML/CSS, un peu de JS.

---

## Quickstart

Prérequis
- Docker (recommandé pour prod / test local)
- Python 3.11 pour développement local
- PostgreSQL avec extension pgvector pour les embeddings (ou Supabase)

Variables d'environnement (exemples)
- DATABASE_URL - URL PostgreSQL (ex: postgres://user:pass@host:5432/dbname)
- SECRET_KEY - clé Django (et clé API pour les devices)
- DEBUG - true|false
- ALLOWED_HOSTS - hôtes autorisés
- EMAIL_BACKEND / SMTP_* - config mail
- MEDIA_ROOT / STATIC_ROOT (optionnel si Docker gère)

Lancer en local (venv)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # ou exporter variables d'env requises
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Lancer en Docker (image prod)
- Construire :
```bash
docker build -t bioattend:latest .
```
- Lancer (exemple minimal)
```bash
docker run -e SECRET_KEY='ma-cle-secrete' -e DATABASE_URL='postgres://...' -p 80:80 bioattend:latest
```
Le conteneur exécute collectstatic, migrate puis démarre Gunicorn (80).

Dockerfile (extrait complet)
```text
name=Dockerfile url=https://github.com/Nde-Code/BioAttendAPP/blob/89417c3feb538bbae52e78e6b008349ae90cdc98/Dockerfile
FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn==21.2.0

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd -m -u 1000 bioattend && \
    mkdir -p /app /app/staticfiles /app/media && \
    chown -R bioattend:bioattend /app

WORKDIR /app

COPY --chown=bioattend:bioattend . .

EXPOSE 80

USER bioattend

CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    gunicorn BioAttend.wsgi:application --bind 0.0.0.0:80 --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile - --log-level info
```

> Notes Docker :
> - Image multi-stage pour réduire la taille.
> - Dépendances système nécessaires pour OpenCV/insightface (libgl, libgomp...).
> - Gunicorn configuré : 4 workers, 2 threads ; timeout 120s — ajuster selon ressources.
> - Le conteneur exécute automatiquement les migrations et collectstatic au démarrage.

---

## Dépendances

Fichier requirements.txt (extrait)
```text
name=requirements.txt url=https://github.com/Nde-Code/BioAttendAPP/blob/ec5b2f0738761f73c6d42939e1a8cbee1a91a95e/requirements.txt
albucore==0.0.24
albumentations==2.0.8
annotated-types==0.7.0
asgiref==3.11.1
certifi==2026.2.25
cffi==2.0.0
...
Django==5.1.15
djangorestframework==3.17.1
pgvector==0.4.2
insightface==0.7.3
opencv-python-headless==4.13.0.92
psycopg2-binary==2.9.11
gunicorn==21.2.0 (installé par Dockerfile)
whitenoise==6.12.0
...
```

Remarques :
- pgvector est utilisé côté DB pour stocker et rechercher les embeddings (CosineDistance).
- insightface + onnxruntime + numpy + opencv sont requis pour la partie IA/embeddings si tu veux exécuter l'extraction localement.
- Certaines bibliothèques (onnxruntime, insightface) dépendent d’artefacts système — vérifier compatibilité CPU / GPU.

---

## API — Documentation complète (/api/)

Préfixe global : toutes les routes API sont incluses sous `/api/` via `BioAttend/urls.py`.

Authentification pour les endpoints API
- Header préféré : Authorization: Bearer <SECRET_KEY>
- Alternatif : X-API-Key: <SECRET_KEY>
- La valeur comparée est `settings.SECRET_KEY`. Si manquante ou invalide, réponse 401.

Les endpoints principaux découverts :
- POST /api/face/identify/
- POST /api/front/events/
- GET, POST /api/schedule/absence-alert/

Détails, validations et exemples ci‑dessous.

---

### 1) POST /api/face/identify/
But : identifier un utilisateur depuis un embedding facial envoyé par une pointeuse (Raspberry Pi/InsightFace), créer un pointage (ENTREE/SORTIE) en production, et renvoyer un feedback de ponctualité.

Endpoint source : api/views.py (FaceIdentifyView)
- URL : /api/face/identify/
- Méthode : POST
- Auth : Authorization Bearer | X-API-Key

Payload JSON attendu :
- embedding (required) : liste de 512 floats — vecteur d'embedding
- ingestion_mode (optional) : "production" (par défaut) ou "test"
  - "test" désactive les effets persistants (création de pointage/alerte)
- fraud_detected (optional) : boolean (défaut false) — si true → rejet (403)
- fraud_reason (optional) : string

Validations & erreurs :
- Si clé API incorrecte → 401
- Si ingestion_mode invalide → 400
- Si embedding manquant / non-liste / mauvaise longueur / valeurs non numériques → 400
- Si fraude détectée → 403 (et enregistre incident si ingestion_mode != test)
- Si pb DB / pgvector → 500

Logique :
- EMBEDDING_SIZE = 512 (constante)
- Recherche du match via pgvector :
  Utilisateur.objects.filter(embedding_facial__isnull=False).annotate(distance=CosineDistance("embedding_facial", embedding)).order_by("distance").first()
- Threshold : settings.FACE_MATCH_THRESHOLD (défaut 0.5 si non défini)
  - Si match.distance > threshold → rejet (404)
  - Si aucun match → 404
- Si matched & production :
  - Calcul du type de pointage suivant via _next_pointage_type_for_pointeuse(utilisateur) (ENTREE/SORTIE)
  - Création d’un Pointage (statut "VALIDE", origine Pointage.ORIGINE_POINTEUSE)
  - build_pointage_feedback(pointage) renvoie messages / flags / worked_duration_display

Réponse (succès 200) :
```json
{
  "matched": true,
  "user_id": "uuid-de-l-utilisateur",
  "username": "jdoe",
  "full_name": "John Doe",
  "distance": 0.123456,
  "pointage_id": "uuid-pointage",
  "pointage_type": "ENTREE",
  "schedule_feedback": ["message1", ...],
  "schedule_flags": ["FLAG_A", ...],
  "worked_duration_display": "7h30",
  "ingestion_mode": "production"
}
```

Réponse (exemples d'erreurs) :
- Embedding manquant :
```json
{ "matched": false, "error": "Le champ 'embedding' est requis." }
```
- Auth manquante :
```json
{ "matched": false, "error": "Authentification requise via Authorization Bearer ou X-API-Key." }
```

Exemple cURL
```bash
curl -X POST https://example.com/api/face/identify/ \
  -H "Authorization: Bearer $SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ingestion_mode":"production","embedding":[0.1, -0.2, ... 512 valeurs ...]}'
```

---

### 2) POST /api/front/events/
But : journaliser des événements venant d'une borne (pointeuse/front) (utilisateur inconnu, échec…).

Endpoint source : api/views.py (FrontEventView)
- URL : /api/front/events/
- Méthode : POST
- Auth : Authorization Bearer | X-API-Key

Payload JSON attendu :
- event_type (required) : "unknown_user" | "recognition_failed" | "spoof_attempt"
  - Map interne : unknown_user → "UTILISATEUR_INCONNU", recognition_failed → "ECHEC_RECONNAISSANCE", spoof_attempt → "TENTATIVE_FRAUDE"
- status (required) : "error" | "rejected" | "blocked"
  - Map interne : ERROR/REJECTED/BLOCKED
- message (required) : string non vide
- device_name (required) : string non vide
- details (optional) : object JSON

Effet :
- Crée un Pointage (utilisateur=None, statut='NON_VALIDE', incident_type = mapping, device_name, details)
- Alerte.create_or_update_for_incident(...) est appelée

Réponses :
- 201 Created (succès) :
```json
{ "logged": true, "event_id": "uuid-pointage", "event_type": "unknown_user", "status": "error" }
```
- 400 Bad Request si champs invalides
- 401 Unauthorized si clé invalide

Exemple cURL
```bash
curl -X POST https://example.com/api/front/events/ \
  -H "Authorization: Bearer $SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "unknown_user",
    "status": "error",
    "message": "Aucun visage trouvé",
    "device_name": "pointeuse-1",
    "details": {"image_cid":"..."}
  }'
```

---

### 3) GET, POST /api/schedule/absence-alert/
But : déclencher la détection d'absences pour un jour donné et l'envoi d'alertes mails (service trigger_absence_alerts_for_day).

Endpoint source : api/views.py (AbsenceAlertView)
- URL : /api/schedule/absence-alert/
- Méthodes : GET (query param `date`) et POST (JSON { "date": "YYYY-MM-DD" })
- Auth : Authorization Bearer | X-API-Key
- Paramètre date (optionnel) format `YYYY-MM-DD`. Si absent, la date utilisée est `timezone.localdate()`.

Réponse (succès 200) :
```json
{
  "checked": true,
  "date": "2026-05-14",
  "absences": [
    {"utilisateur_id": "...", "nom": "Dupont", "shift": "..."},
    ...
  ]
}
```
Erreurs :
- 400 si date mal formée
- 401 si clé invalide
- 500 si erreur interne (le code journalise l'exception)

Exemples :
- GET : `/api/schedule/absence-alert/?date=2026-05-14`
- POST body : `{"date": "2026-05-14"}`

---

## Routes web (UI) — résumé des urls principales

Les urls HTML sont déclarées dans les modules suivants (préfixe racine tel que défini dans `BioAttend/urls.py`).

BioAttend/urls.py (inclut)
- / (core.urls)
- /dashboard/ (dashboard.urls)
- /accounts/ (accounts.urls + django.contrib.auth.urls)
- /Employee/ (Employee.urls)
- /api/ (api.urls)  ← API expliqué ci‑dessus
- /schedule/ (schedule.urls)

Extrait des routes importantes (UI) :
- core:
  - GET / → page d'accueil
- dashboard:
  - GET /dashboard/ → tableau de bord principal
  - GET /dashboard/presents-aujourdhui/
  - GET /dashboard/absents-aujourdhui/
  - etc.
- accounts:
  - /accounts/login/
  - /accounts/settings/
  - /accounts/password/change/
- Employee:
  - /Employee/utilisateurs/ (liste)
  - /Employee/utilisateurs/ajouter/
  - /Employee/utilisateurs/<uuid>/modifier/
  - /Employee/pointages/, /Employee/pointages/export-csv/
  - /Employee/alertes/
- schedule:
  - /schedule/ (home)
  - /schedule/submit/
  - /schedule/export/csv/
  - /schedule/settings/
  - /schedule/requests/<uuid>/approve/ et /reject/

(Consulte les fichiers `*/urls.py` pour la liste complète des routes et noms d'URL.)

---

## Structure du dépôt (vue d'ensemble)

Arborescence clé (simplifiée)
- BioAttend/                - projet Django (settings, urls, wsgi)
- api/
  - urls.py                - déclaration des endpoints API (/api/...)
  - views.py               - implémentation de FaceIdentifyView, FrontEventView, AbsenceAlertView
  - tests.py               - tests unitaires pour l'API (FaceIdentify)
- accounts/                 - gestion des comptes & vues d'auth
- core/                     - page d'accueil, middleware utilitaires
- dashboard/                - vues du tableau de bord
- Employee/                 - gestion utilisateurs & pointages (UI)
- schedule/                 - gestion demandes planning, alertes
- attendance/               - modèles de pointage
- alerts/                   - modèle & logique d'alertes
- requirements.txt
- Dockerfile
- manage.py

Explication des composants principaux
- api/views.py : logique d'API utilisée par les pointeuses.
- accounts, Employee, schedule, dashboard : vues web et formulaires (UI).
- attendance.models.Pointage : modèle représentant un pointage ; utilisé/produit par l'API.
- alerts.models.Alerte : centralise la création / mise à jour des alertes d'incident.
- schedule.services : contient build_pointage_feedback et trigger_absence_alerts_for_day.

---

## Tests

- Tests unitaires pour l'API se trouvent dans `api/tests.py`. Ils couvrent validation d'input, auth et une partie du flux d'identification.
- Lancer tests :
```bash
python manage.py test
```
- Le projet utilise `override_settings` pour isoler la configuration API durant les tests (ex: SECRET_KEY de test).

---

## Développement & bonnes pratiques

- Mode ingestion:
  - Utiliser `ingestion_mode: "test"` pour tester sans créer de pointages/alertes persistants.
- Logging et diagnostic:
  - Le projet contient des headers HTTP de diagnostic (middleware) qui exposent `X-BioAttend-Duration-ms`, `X-BioAttend-DB-Queries`, etc. utiles pour profiler.
- Requêtes PG / performances:
  - La recherche d'embeddings utilise pgvector ; vérifie les indexes et la configuration Postgres pour performances (index pgvector si nécessaire).
- Sécurité:
  - La clé API est `SECRET_KEY` ; pour un déploiement à long terme il est recommandé d’extraire une clé API dédiée et d’implémenter scopes / rotation.
- CI / Lint:
  - Ajouter flake8/ruff et un job CI pour tests + lint est recommandé.

---

## Déploiement & exploitation

- Production : exécuter le conteneur Docker exposant le port 80 derrière un reverse-proxy (Nginx) si nécessaire.
- DB : PostgreSQL avec pgvector (ou Supabase) est requis.
- Stockage média : configurer MEDIA_ROOT / stockage cloud (S3, supabase storage) en prod.
- Migrations automatiques : Dockerfile exécute `python manage.py migrate --noinput` au démarrage — option pratique mais attention aux migrations concurrentes en scale-out.
- Backups : planifier sauvegarde PostgreSQL régulière (embeddings inclus).

---

## FAQ & dépannage rapide

Q : L’API retourne 401 pour la pointeuse même si la clé semble correcte  
A : Vérifier que la valeur envoyée dans Authorization: Bearer <SECRET_KEY> correspond exactement à settings.SECRET_KEY. Le code utilise secrets.compare_digest() (sensible à la moindre différence).

Q : Recherche pgvector lente  
A : S’assurer que pgvector est bien configuré et que les colonnes d’embedding sont indexées (migrer/ajouter index si nécessaire).

Q : Embeddings invalides (taille autre que 512)  
A : L’API vérifie EMBEDDING_SIZE = 512 et rejettera toute taille différente (400).

---

## Contribuer

1. Fork & branch feature/bugfix.
2. Ajouter des tests pour les changements.
3. Ouvrir PR avec description et checklist.
4. Respecter les règles de formatting (black/ruff recommandés).

---

## Ressources & références

- InsightFace : framework pour extraction d’embeddings.
- pgvector : stockage / recherche d’embeddings dans Postgres.
- Django REST Framework : base des endpoints API.

---

## Licence

(Vérifier et remplir la licence appropriée: ex. MIT / AGPL / proprietaire)
