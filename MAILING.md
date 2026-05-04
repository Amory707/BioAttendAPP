# Système d'alerte par mail

Ce document explique le fonctionnement du système d'alerte par mail de BioAttend, et comment il a été implémenté.

## Objectif

Le système doit envoyer des notifications par mail aux responsables RH (`admin` et `acces_total`) dans les cas suivants :

- une absence détectée pour un jour où l'employé doit être présent
- un retard détecté le jour même

Pour les retards, l'employé concerné est ajouté en copie (`CC`).

## Où le code est implémenté

- `BioAttend/settings.py`
  - configuration des variables d'environnement Brevo
- `schedule/services.py`
  - logique de détection des absences et retards
  - création des alertes en base
  - envoi des mails via l'API Brevo
- `schedule/management/commands/sync_schedule_alerts.py`
  - commande Django pour synchroniser les alertes
- `api/views.py`
  - pointage créé via API appelle `build_pointage_feedback()`
  - cela appelle `sync_schedule_alerts()` pour la journée concernée et peut déclencher l'envoi d'un mail de retard/absence
- `api/schedule/absence-alert/`
  - nouvel endpoint API pour déclencher manuellement la détection d'absence et l'envoi de mail si la journée est terminée

## Déclenchement de l'envoi de mail

Le système n'a pas de scheduler interne intégré dans le code. L'envoi de mail se déclenche lorsque l'un des chemins suivants exécute `sync_schedule_alerts()` :

- en manuel via la commande Django `python manage.py sync_schedule_alerts --start=YYYY-MM-DD --end=YYYY-MM-DD`
- automatiquement depuis l'API de pointage biométrique lors de la création d'un pointage, via `api/views.py` qui appelle `build_pointage_feedback(pointage)`

Dans les deux cas, la logique est :

1. `sync_schedule_alerts()` analyse les jours par utilisateur
2. il crée une alerte `Alerte` (`ABSENCE` ou `RETARD`) en base si nécessaire
3. si l'alerte est créée pour le jour courant (`today`), alors le mail est envoyé immédiatement

> Important : pour les jours passés, l'alerte est créée en base, mais l'envoi de mail n'est pas déclenché.

### Planification automatique recommandée

Pour que l'alerte d'absence soit envoyée automatiquement sans intervention humaine, il faut planifier l'exécution quotidienne de la commande après la fin du créneau de travail fixé dans `ScheduleSettings.departure_window_end`.

Par défaut, le créneau de fin de journée est `18:00` dans `schedule/models.py`.

Exemple de cron journalier :

```cron
5 18 * * * cd /workspaces/BioAttendAPP && ./.venv/bin/python manage.py sync_schedule_alerts --start=$(date +\%F) --end=$(date +\%F)
```

Ou, si le déploiement est exécuté le matin suivant, le job peut être lancé pour la date d'hier :

```cron
5 0 * * * cd /workspaces/BioAttendAPP && ./.venv/bin/python manage.py sync_schedule_alerts --start=$(date -d 'yesterday' +\%F) --end=$(date -d 'yesterday' +\%F)
```

### Nouvelle API d'alerte d'absence

Une alternative plus flexible à la crontab est d'appeler le nouvel endpoint HTTP :

- `GET /api/schedule/absence-alert/`
- authentification : `Authorization: Bearer <SECRET_KEY>` ou `X-API-Key: <SECRET_KEY>`

Paramètres de requête :

- `date` : date de la journée à analyser au format `YYYY-MM-DD`
  - optionnel : si absent, la valeur par défaut est aujourd'hui

Exemples `curl` :

```bash
curl "https://ton-domaine/api/schedule/absence-alert/?date=2026-04-21" \
  -H "Authorization: Bearer $SECRET_KEY"
```

ou sans date (par défaut aujourd'hui) :

```bash
curl "https://ton-domaine/api/schedule/absence-alert/" \
  -H "Authorization: Bearer $SECRET_KEY"
```

Ce endpoint vérifie tous les utilisateurs employés pour la date donnée, retourne la liste de ceux dont la journée est terminée et qui n'ont pas pointé, crée l'alerte d'absence en base si nécessaire, et envoie le mail de notification côté back-end.

Réponse JSON attendue :

```json
{
  "checked": 42,
  "date": "2026-04-21",
  "absences": [
    {
      "user_id": "uuid-de-l-utilisateur",
      "username": "jdupont",
      "full_name": "Jean Dupont",
      "alert_created": true,
      "email_sent": true,
      "description": "Absence detectee pour Jean Dupont le 21/04/2026.",
      "reason": ""
    }
  ]
}
```

Tu peux appeler cette API depuis un service de scheduler HTTP comme Cronitor, GitHub Actions, un service cloud (AWS EventBridge, Azure Logic Apps, Google Cloud Scheduler), ou n'importe quel planificateur HTTP. Le backend se charge d'envoyer les mails pour les absences détectées.

> Cronitor est une bonne option ici, mais ce n'est pas obligatoire : il suffit d'un service capable de faire un simple GET authentifié.

Cette planification garantit que les absences du jour sont détectées après la fin de journée et que l'envoi de mail devient automatique.

## Configuration requise

Les variables suivantes doivent être définies dans le fichier `.env` :

```dotenv
DEFAULT_FROM_EMAIL=no-reply@bioattend.local
BREVO_API_KEY=cle_api_brevo
BREVO_SENDER_EMAIL=contact@tondomaine.com
BREVO_SENDER_NAME=BioAttend
BREVO_API_ENDPOINT=https://api.brevo.com/v3/smtp/email
```

- `DEFAULT_FROM_EMAIL` : adresse de secours si `BREVO_SENDER_EMAIL` n'est pas précisé.
- `BREVO_API_KEY` : clé API privée Brevo.
- `BREVO_SENDER_EMAIL` : adresse e-mail utilisée comme expéditeur.
- `BREVO_SENDER_NAME` : nom affiché comme expéditeur.
- `BREVO_API_ENDPOINT` : URL API Brevo, normalement laissée par défaut.

## Comment les destinataires sont choisis

Le système récupère les adresses e-mail des utilisateurs qui ont le rôle :

- `admin`
- `acces_total`

Cette logique se trouve dans `schedule/services.py` avec la fonction `get_rh_recipient_emails()`.

Seuls les utilisateurs avec un champ `email` renseigné sont inclus.

## Détails du fonctionnement

### Détection d'absence

La détection s'appuie sur `analyze_day(utilisateur, target_day)` dans `schedule/services.py`.

Un employé est considéré comme absent si :

- il doit être présent ce jour-là (`required_presence` vrai)
- il n'a pas de pointage valide ce jour
- la journée est passée (`target_day < today`) ou bien il est aujourd'hui et l'heure actuelle est supérieure ou égale à `departure_window_end`

En pratique, cela signifie que :

- le dashboard peut déjà afficher des absents aujourd'hui
- l'alerte mail d'absence n'est envoyée que si on est après la fin de la journée définie ou pour un jour antérieur

### Détection de retard

Un retard est détecté si :

- un pointage d'entrée valide existe
- l'heure d'entrée est supérieure à `arrival_window_end`
- il n'y a pas de demande de retard approuvée pour ce jour

Le retard est envoyé le jour même.

### Création d'alertes en base

Quand une absence ou un retard est identifié par `sync_schedule_alerts()`, une ligne `Alerte` est créée dans la table `alertes` avec :

- `type='ABSENCE'` pour une absence
- `type='RETARD'` pour un retard

La création est unique par utilisateur/jour grâce à la recherche du `day_token` dans la description.

## Envoi d'emails Brevo

Le code de l'envoi se trouve dans `schedule/services.py` :

- `_send_email_via_brevo(...)`
- `_send_absence_notification(...)`
- `_send_late_notification(...)`

### Corps des mails

- Les mails sont envoyés en HTML et en texte.
- Les mails d'absence sont adressés aux RH.
- Les mails de retard sont adressés aux RH avec l'employé en copie.

### Conditions d'envoi

Un mail est envoyé uniquement si :

- une alerte est créée pour le jour courant
- il y a des adresses RH valides
- la clé Brevo est présente


## Commande de test

Pour vérifier le système, utilisez :

```bash
python manage.py sync_schedule_alerts --start=YYYY-MM-DD --end=YYYY-MM-DD
```

### Exemple pour tester hier

```bash
python manage.py sync_schedule_alerts --start=$(date -d 'yesterday' +%F) --end=$(date -d 'yesterday' +%F)
```

### Exemple pour tester aujourd'hui

```bash
python manage.py sync_schedule_alerts --start=$(date +%F) --end=$(date +%F)
```

> Note : pour une absence d'aujourd'hui, l'alerte mail ne sera créée que si l'heure actuelle est passée après `departure_window_end`.

## Validation

Pour vérifier que le système fonctionne :

1. Assure-toi que `BREVO_API_KEY` est valide.
2. Assure-toi que les utilisateurs RH ont un e-mail rempli en base.
3. Lance la commande `sync_schedule_alerts` pour une date de test.
4. Vérifie que la table `Alerte` contient les alertes attendues.
5. Vérifie la console Brevo ou le dashboard Brevo pour le mail envoyé.

## Points importants

- Le dashboard de présence (`dashboard/absents-aujourdhui/`) n'est pas le même mécanisme que les alertes mail.
- Le dashboard affiche simplement les employés qui n'ont pas pointé aujourd'hui.
- Les mails sont envoyés exclusivement à partir de la création d'une alerte dans `sync_schedule_alerts()`.

## Évolution possible

Si tu veux, on peut faire évoluer le système pour :

- envoyer les absences plus tôt dans la journée
- ajouter un envoi automatique toutes les nuits
- créer une table de logs d'envoi mail
- ajouter des notifications par Slack ou par API interne
