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
