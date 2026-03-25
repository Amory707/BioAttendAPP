# App `api` — BioAttend Face Identification API

Fournit un endpoint REST permettant au **Raspberry Pi** d'identifier un employé
à partir d'un embedding facial extrait localement par InsightFace.

---

## Architecture du pipeline

```
Raspberry Pi                          Serveur Django (cette app)
────────────────────────────          ────────────────────────────────────────
📷 Caméra capture une image
        ↓
🧠 InsightFace (local sur le Pi)
   → détecte le visage
   → extrait l'embedding (512 floats)
        ↓
📡 POST /api/face/identify/   ──────→  📥 Reçoit { "embedding": [...] }
   JSON { "embedding": [...] }                ↓
                                       🔍 pgvector : CosineDistance
                                          contre Utilisateur.embedding_facial
                                          ORDER BY distance LIMIT 1
                                                ↓
                               distance < seuil ?
                               ┌─── OUI ──────────────────────────────┐
                               │  200 { matched: true, username: ... } │
                               └───────────────────────────────────────┘
                               ┌─── NON ──────────────────────────────┐
  ←──────────────────────────  │  404 { matched: false, error: ... }  │
                               └───────────────────────────────────────┘
```

**Le traitement visuel (capture + extraction d'embedding) se fait entièrement
sur le Raspberry Pi.** Le serveur ne reçoit que le vecteur numérique.

---

## Endpoint

### `POST /api/face/identify/`

#### Requête

```
Content-Type: application/json
```

```json
{
  "embedding": [0.123, -0.456, 0.789, ...]
}
```

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `embedding` | liste de floats | Oui | Vecteur 512 dimensions produit par InsightFace |

#### Réponses

**200 — Visage reconnu**
```json
{
  "matched": true,
  "user_id": "80c316eb-d03d-4acf-94aa-272356a888da",
  "username": "jean.dupont",
  "full_name": "Jean Dupont",
  "distance": 0.18
}
```

| Champ | Description |
|---|---|
| `matched` | `true` si un utilisateur correspond |
| `user_id` | UUID de l'utilisateur en base |
| `username` | Identifiant de connexion Django |
| `full_name` | Prénom + Nom de l'employé |
| `distance` | Distance cosinus (0 = identique, plus petit = plus proche) |

**404 — Aucune correspondance**
```json
{
  "matched": false,
  "error": "Aucun visage correspondant trouvé."
}
```

**400 — Requête invalide**
```json
{
  "matched": false,
  "error": "L'embedding doit avoir exactement 512 dimensions, 100 reçues."
}
```

**500 — Erreur serveur**
```json
{
  "matched": false,
  "error": "Erreur interne du serveur."
}
```

---

## Codes HTTP

| Cas | Code |
|---|---|
| Visage reconnu | `200` |
| Champ manquant / mauvaise taille / valeur non numérique | `400` |
| Aucun visage correspondant (inconnu) | `404` |
| Erreur base de données ou serveur | `500` |

---

## Configuration

Dans `BioAttend/settings.py` :

```python
# Seuil de distance cosinus en dessous duquel un visage est considéré reconnu.
# Entre 0 (identique) et 2 (opposé). Recommandé : 0.4 – 0.6
FACE_MATCH_THRESHOLD = 0.5
```

Ajuster ce seuil selon les conditions réelles de capture :
- **Seuil trop bas (ex : 0.2)** → trop strict, risque de refuser des visages valides
- **Seuil trop haut (ex : 0.8)** → trop laxiste, risque de confondre deux personnes

---

## Enrôler un utilisateur

Avant de pouvoir identifier un employé, il faut enregistrer son embedding en base.

Depuis le shell Django :

```bash
python manage.py shell
```

```python
from accounts.models import Utilisateur

user = Utilisateur.objects.get(username="jean.dupont")

# embedding produit par InsightFace sur le Raspberry Pi lors de l'enrôlement
embedding_list = [0.123, -0.456, ...]  # liste de 512 floats

user.embedding_facial = embedding_list
user.save(update_fields=["embedding_facial"])
```

---

## Tester en local

### Prérequis

```bash
# Appliquer les migrations
python manage.py migrate

# Lancer le serveur
python manage.py runserver
```

### Test rapide avec curl

```bash
# Générer un embedding aléatoire et l'envoyer
python -c "import json, random; print(json.dumps({'embedding': [random.uniform(-1,1) for _ in range(512)]}))" \
  | curl -s -X POST http://localhost:8000/api/face/identify/ \
         -H "Content-Type: application/json" \
         -d @- | python -m json.tool
```

### Simulation complète (InsightFace → DB → API)

```bash
# Simule exactement le comportement du Raspberry Pi
python simulate_face.py
```

Ce script :
1. Charge InsightFace (`buffalo_s`) localement
2. Détecte le visage dans une image réelle (`t1.jpg`)
3. Extrait l'embedding (512 dims)
4. Enregistre l'embedding en base pour un utilisateur de test
5. Appelle l'API et vérifie la réponse

### Exemple depuis le Raspberry Pi

```python
import requests

# embedding extrait par InsightFace sur le Pi
embedding = face.embedding.tolist()  # list de 512 floats

response = requests.post(
    "http://<ip-serveur>:8000/api/face/identify/",
    json={"embedding": embedding},
    timeout=5,
)

data = response.json()

if data["matched"]:
    print(f"Bonjour {data['full_name']} !")
else:
    print("Visage non reconnu.")
```

---

## Structure des fichiers

```
api/
├── views.py      # FaceIdentifyView — logique de l'endpoint
├── urls.py       # Route : /api/face/identify/
├── apps.py       # Déclaration de l'app Django
└── README.md     # Ce fichier
```

---

## Dépendances

| Package | Rôle |
|---|---|
| `djangorestframework` | Framework API REST |
| `pgvector` | Recherche de voisin le plus proche en base PostgreSQL |
| `insightface` | Extraction d'embeddings faciaux (côté Raspberry Pi) |
| `onnxruntime` | Moteur d'inférence pour les modèles InsightFace |
