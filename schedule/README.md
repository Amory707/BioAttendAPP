# App Emploi du temps

Cette app gère :

- les demandes de congé, retard et autre soumises par les employés ;
- l’encodage des maladies par les RH ;
- le calendrier des absences / congés / jours fériés belges ;
- l’export CSV ;
- le contrôle des retards, départs anticipés, journées trop courtes et absences.

## Modèles

- `ScheduleRequest` : demande ou encodage RH.
- `ScheduleSettings` : configuration globale et interrupteur d’activation.

## Vue principale

- `/schedule/` : calendrier et gestion des demandes.

## Commande utile

- `python manage.py sync_schedule_alerts` : synchronise les alertes d’absence et de ponctualité.
  - ce job doit être exécuté automatiquement chaque jour après la fin du créneau de travail (`departure_window_end`) pour envoyer les mails d’absences sans intervention manuelle.
