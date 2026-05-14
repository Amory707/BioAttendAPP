# 🧬 BioAttend

Plateforme de pointage biométrique (reconnaissance faciale), gestion des plannings et alertes RH.

---

## Table des matières

- [Présentation](#présentation)
- [Quickstart](#quickstart)
  - [Prérequis](#prérequis)
  - [Démarrage local (venv)](#démarrage-local-venv)
  - [Démarrage avec Docker](#démarrage-avec-docker)
- [Variables d'environnement](#variables-denvironnement)
  - [Variables obligatoires](#variables-obligatoires)
  - [Variables optionnelles & mail (Brevo)](#variables-optionnelles--mail-brevo)
- [Dockerfile & déploiement](#dockerfile--déploiement)
- [Dépendances principales](#dépendances-principales)
- [API — Documentation complète (/api/)](#api---documentation-complète-api)
  - [POST /api/face/identify/](#post-apifaceidentify)
  - [POST /api/front/events/](#post-apifrontevents)
  - [GET, POST /api/schedule/absence-alert/](#get-post-apischeduleabsence-alert)
- [Routes Web (UI) — aperçu](#routes-web-ui--aperçu)
- [Structure du dépôt](#structure-du-dépôt)
- [Envoi d'emails & Brevo (détails)](#envoi-demails--brevo-détails)
- [Tests](#tests)
- [Bonnes pratiques & exploitation](#bonnes-pratiques--exploitation)
- [FAQ & dépannage rapide](#faq--dépannage-rapide)
- [Contribuer](#contribuer)
- [Licence](#licence)

---

## Présentation

BioAttend gère :
- la capture et l'identification faciale depuis des pointeuses (Raspberry Pi + InsightFace),
- la création et le suivi des pointages (ENTREE / SORTIE),
- la détection d'absences et de retards,
- l'envoi d'alertes e‑mail (via Brevo),
- une interface web d'administration et des exports CSV.

Le backend est une application Django + Django REST Framework. Les embeddings sont stockés dans PostgreSQL via l'extension pgvector.

---

## Quickstart

### Prérequis
- Python 3.11 (dev)
- PostgreSQL (pgvector recommandé) ou Supabase
- Docker (recommandé pour production)
- Clé API Brevo si envoi d'emails nécessaire

### Démarrage local (venv)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# générer .env (voir .devcontainer/generate-env.sh ou copier .env.example)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Démarrage avec Docker
Construction :
```bash
docker build -t bioattend:latest .
```
Exécution (exemple minimal) :
```bash
docker run -e SECRET_KEY='ma-cle' -e DATABASE_URL='postgres://user:pass@host:5432/db' -p 80:80 bioattend:latest
```
Le container exécute automatiquement `collectstatic` et `migrate` puis démarre Gunicorn.

---

## Variables d'environnement

Le projet utilise django-environ. Voici les variables principales (fournies par `.devcontainer/generate-env.sh` et utilisées dans `BioAttend/settings.py`).

Variables obligatoires / importantes
- SECRET_KEY — clé Django (également utilisée comme clé API pour les devices dans l'état actuel)
- DATABASE_URL — URL de connexion PostgreSQL (ex : `postgres://user:pass@host:5432/db`)
- DEBUG — `True`/`False`
- ALLOWED_HOSTS — hôtes autorisés (string ou liste)

Variables liées au mail / Brevo
- DEFAULT_FROM_EMAIL — adresse par défaut (`no-reply@bioattend.local` si absent)
- BREVO_API_KEY — clé API Brevo (nécessaire pour envoyer des e‑mails)
- BREVO_SENDER_EMAIL — adresse expéditeur (ex: `contact@mondomaine.com`)
- BREVO_SENDER_NAME — nom expéditeur (ex: `BioAttend`)
- BREVO_API_ENDPOINT — URL Brevo (par défaut `https://api.brevo.com/v3/smtp/email`)

Autres variables utiles
- SUPABASE_URL / SUPABASE_KEY — si vous utilisez Supabase
- MEDIA_ROOT / STATIC_ROOT — emplacements pour fichiers et médias

Exemple `.env` minimal (ne pas committer):
```dotenv
SECRET_KEY="changeme"
DEBUG=True
DATABASE_URL="postgres://user:pass@db:5432/bioattend"
DEFAULT_FROM_EMAIL="no-reply@bioattend.local"
BREVO_API_KEY="votre_cle_brevo"
BREVO_SENDER_EMAIL="contact@exemple.com"
BREVO_SENDER_NAME="BioAttend"
```

---

## Dockerfile & déploiement

Le Dockerfile fourni est multi-stage et optimisé pour produire une image légère avec un environnement virtuel préinstallé.

Points clés :
- Image de base : `python:3.11-slim`
- Dépendances système pour OpenCV / insightface (libgl, libgomp, libsm6, ...)
- Pip installe `requirements.txt` puis `gunicorn`
- Au démarrage : `collectstatic`, `migrate`, puis Gunicorn lancé sur le port 80
- Utilisateur non-root `bioattend` (UID 1000)

Extrait (voir Dockerfile complet dans le repo) :
```dockerfile
FROM python:3.11-slim as builder
# ... apt-get + installation deps python ...
COPY requirements.txt .
RUN pip install -r requirements.txt && pip install gunicorn==21.2.0
FROM python:3.11-slim
# ... copy venv, add user, expose, CMD ...
```

Conseils :
- Protéger SECRET_KEY et DATABASE_URL via le gestionnaire de secrets de votre orchestrateur.
- Garder `migrate` automatique pour déploiements simples ; pour environnements multi-instances utiliser stratégie de migration contrôlée.

---

## Dépendances principales

Fichier : `requirements.txt` (extraits)
- Django==5.1.15
- djangorestframework==3.17.1
- pgvector==0.4.2
- insightface==0.7.3
- onnxruntime, numpy, opencv-python-headless
- psycopg2-binary
- gunicorn (installé via Dockerfile)
- whitenoise (servir les static en production simple)

Remarque : certaines dépendances d'IA (insightface, onnxruntime) peuvent nécessiter des paquets natifs ou version spécifique selon CPU/GPU.

---

## API — Documentation complète (/api/)

Préfixe global : `/api/` (défini dans `BioAttend/urls.py`).

Authentification
- Header `Authorization: Bearer <SECRET_KEY>` ou `X-API-Key: <SECRET_KEY>`
- Le code compare la valeur à `settings.SECRET_KEY` via `secrets.compare_digest`

Types de réponses standard : JSON. Erreurs retournent des codes HTTP appropriés (400, 401, 403, 404, 500).

---

### POST /api/face/identify/
But : identification faciale envoyée par la pointeuse. En production, crée un `Pointage` validé.

- Méthode : POST
- Auth : Bearer / X-API-Key
- Payload JSON :
  - `embedding` (required) : liste de 512 floats
  - `ingestion_mode` (optional) : `"production"` (défaut) ou `"test"` (désactive persistance)
  - `fraud_detected` (optional) : bool — si `true` retourne 403
  - `fraud_reason` (optional) : string
- Validations :
  - Embedding taille = 512, éléments numériques → sinon 400
  - ingestion_mode doit être `production` ou `test` → sinon 400
- Logique :
  - Recherche du meilleur match via `pgvector` : cosine distance
  - Seuil : `settings.FACE_MATCH_THRESHOLD` (0.5 par défaut)
  - Si correspondance et `production` : création de `Pointage` (statut `VALIDE`), calcul du feedback ponctualité via `build_pointage_feedback`
- Réponses :
  - 200 (succès) : JSON avec `matched: true`, `user_id`, `username`, `distance`, `pointage_id`, `pointage_type`, `schedule_feedback`, `worked_duration_display`, …
  - 400 : payload invalide
  - 401 : auth manquante / invalide
  - 403 : fraude détectée
  - 404 : pas de correspondance
  - 500 : erreur serveur (ex : pgvector)

Exemple (cURL) :
```bash
curl -X POST https://host/api/face/identify/ \
  -H "Authorization: Bearer $SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ingestion_mode":"production","embedding":[0.0,0.1,...512 valeurs...] }'
```

---

### POST /api/front/events/
But : journaliser un événement depuis la borne (ex: utilisateur inconnu, tentative de spoof, échec de reconnaissance).

- Méthode : POST
- Auth : Bearer / X-API-Key
- Payload JSON requis :
  - `event_type` : `unknown_user` | `recognition_failed` | `spoof_attempt`
  - `status` : `error` | `rejected` | `blocked`
  - `message` : string non vide
  - `device_name` : string non vide
  - `details` : object (optionnel)
- Effet :
  - Crée un `Pointage` non validé (`statut='NON_VALIDE'`) avec `incident_type` mappé
  - Appelle `Alerte.create_or_update_for_incident(...)`
- Réponses :
  - 201 Created (succès) : `{ "logged": true, "event_id": "...", "event_type": "...", "status": "..." }`
  - 400 : params invalides
  - 401 : auth invalide

Exemple :
```bash
curl -X POST https://host/api/front/events/ \
  -H "Authorization: Bearer $SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event_type":"unknown_user","status":"error","message":"Pas de visage","device_name":"pointeuse-1"}'
```

---

### GET, POST /api/schedule/absence-alert/
But : déclencher la détection d'absences/retards pour un jour donné et (si nécessaire) envoyer des emails via Brevo.

- Méthodes :
  - GET `/api/schedule/absence-alert/?date=YYYY-MM-DD`
  - POST `/api/schedule/absence-alert/` avec JSON `{ "date": "YYYY-MM-DD" }`
- Auth : Bearer / X-API-Key
- Paramètre `date` : facultatif, format `YYYY-MM-DD`. Si absent → date locale (`timezone.localdate()`).
- Effet :
  - Appelle `trigger_absence_alerts_for_day(date)` (dans `schedule/services.py`)
  - Crée en base les `Alerte` correspondantes et envoie mails RH (si configuré)
- Réponses :
  - 200 : `{ "checked": <int|bool>, "date":"YYYY-MM-DD", "absences":[ ... ] }`
  - 400 : date invalide
  - 401 : auth invalide
  - 500 : erreur si l'envoi mail échoue par exemple

---

## Routes Web (UI) — aperçu

Les urls UI principales se trouvent dans les apps :
- `core/` → `/` (accueil)
- `dashboard/` → `/dashboard/` (tableau de bord, listes presents/absents, export CSV)
- `accounts/` → `/accounts/login/`, `/accounts/settings/`...
- `Employee/` → `/Employee/utilisateurs/`, `/Employee/pointages/`, export CSV, etc.
- `schedule/` → `/schedule/`, `/schedule/submit/`, `/schedule/settings/`...
- `api/` → endpoints décrits ci‑dessus

Consultez `*/urls.py` pour la liste exhaustive et les noms de routes.

---

## Structure du dépôt (résumé)

- BioAttend/ — settings, urls, wsgi
- api/
  - urls.py
  - views.py (FaceIdentifyView, FrontEventView, AbsenceAlertView)
  - tests.py
- accounts/, Employee/, dashboard/, core/, schedule/, attendance/, alerts/ — apps Django
- requirements.txt
- Dockerfile
- .devcontainer/ (scripts d'initialisation .env)

---

## Envoi d'emails & Brevo (détails opérationnels)

Le projet utilise l'API SMTP de Brevo via un POST JSON. Comportement principal :
- Fonctions d'envoi dans `schedule/services.py` :
  - `_send_email_via_brevo(subject, html_content, to_emails, cc_emails=None)`
  - `_send_absence_notification(...)`, `_send_late_notification(...)`
- Préconditions :
  - `settings.BREVO_API_KEY` doit être renseignée
  - Destinataires RH sont résolus via `get_rh_recipient_emails()` (utilisateurs avec rôle `admin` ou `acces_total` et email)
- Payload envoyé :
```json
{
  "sender": { "name": "BioAttend", "email": "no-reply@..." },
  "to": [{"email": "rh@example.com"}],
  "cc": [{"email": "employee@example.com"}],   // optionnel
  "subject": "Alerte absence ...",
  "htmlContent": "<p>...</p>",
  "textContent": "..."
}
```
- Headers : `accept: application/json`, `api-key: <BREVO_API_KEY>`
- Erreurs : `requests.RequestException` est capturée et transformée en `EmailDeliveryError` ; l'appelant reçoit un 500 si l'envoi échoue lors du déclenchement d'alertes.

Tests :
- Les tests unitaires patchent `requests.post` et vérifient que le payload contient `subject`, `cc`, `htmlContent`, etc.

Recommandations :
- Utiliser une clé Brevo dédiée au service.
- Surveiller les quotas/erreurs 4xx et 5xx retournés par Brevo.
- En production, logguer les échecs d'envoi et mettre en place une file de retry si besoin.

---

## Tests

- Lancer : `python manage.py test`
- Les tests importants :
  - `api/tests.py` — validation et flux FaceIdentify, AbsenceAlert
  - `schedule/tests.py` — envoi d'email, création d'alertes
- Les tests utilisent `override_settings` pour fournir `BREVO_API_KEY` factice et patchent `requests.post`.

---

## Bonnes pratiques & exploitation

- Ne pas utiliser `SECRET_KEY` comme unique clé API pour la production : prévoir une clé dédiée et un mécanisme d'authentification des devices plus robuste.
- Indexer correctement les colonnes utilisées par pgvector pour améliorer les temps de recherche.
- Exposer des métriques de performance (middleware intégré fournit `X-BioAttend-Duration-ms`, `X-BioAttend-DB-Queries`, `X-BioAttend-DB-ms`).
- Mettre en place monitoring sur les jobs d'envoi mail et sur les erreurs d'IA (insightface/onnxruntime).
- Sauvegarder régulièrement la base (embeddings inclus).

---

## FAQ & dépannage rapide

Q : La pointeuse reçoit un 401 alors que la clé est correcte  
A : Vérifier le header exact envoyé (`Authorization: Bearer <SECRET_KEY>` ou `X-API-Key`). La comparaison est stricte.

Q : Les emails Brevo ne partent pas  
A : Vérifier `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` et la réponse HTTP renvoyée par Brevo (logs). En cas d'exception, le code remonte l'erreur (500).

Q : Recherche d’embeddings lente  
A : Vérifier pgvector et l'indexation, et évaluer le plan d'exécution côté PostgreSQL.

---

## Contribuer

1. Fork & branch (ex: `feature/ma-modif`)
2. Ajouter tests & documentation
3. Ouvrir PR décrivant les changements
4. Respecter linting / formatting (black / ruff recommandés)

---

## Licence

À préciser (MIT / AGPL / proprietaire). Ajoutez un fichier `LICENSE` adapté.

---

Merci — j’ai parcouru les sources (`api/urls.py`, `api/views.py`, `api/tests.py`, `schedule/services.py`, `BioAttend/settings.py`, `Dockerfile`, `requirements.txt`, etc.) pour produire cette documentation. 

Si tu veux, je peux :
- committer ce README directement dans une branche `docs/readme` et ouvrir une PR,
- générer un fichier OpenAPI (YAML) minimal pour les 3 endpoints API,
- ajouter une collection Postman / example requests dans `docs/`.

Dis‑moi quelle option tu préfères et je m'occupe de la suite.
