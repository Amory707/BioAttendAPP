# Correction de lenteur

## Contexte

Le site BioAttend etait lent en production, surtout sur les pages statistiques,
historiques et dashboard. Une page statistiques a ete mesuree a environ 20
secondes.

Les headers de diagnostic ajoutes a l'application ont donne ces valeurs:

- `X-BioAttend-Duration-ms`: 20685.1 ms
- `X-BioAttend-DB-Queries`: 596 requetes
- `X-BioAttend-DB-ms`: 17532.3 ms

Cela montre que la lenteur venait principalement des acces base de donnees:
la page passait environ 17,5 secondes dans la DB et executait beaucoup trop de
petites requetes.

## Cause principale

L'application est hebergee sur Hetzner en Allemagne, tandis que la base de
donnees Supabase PostgreSQL est en Irlande.

Cette distance n'est pas un probleme si une page fait peu de requetes. Par
contre, elle devient tres visible quand une page Django declenche des centaines
de requetes successives.

Le probleme principal etait donc un comportement de type `N+1 queries`:

- la page chargeait une liste de pointages;
- pour chaque pointage, elle recalculait les informations de planning;
- ce recalcul appelait `analyze_day()`;
- `analyze_day()` faisait lui-meme des requetes `Pointage` et `ScheduleRequest`;
- le total montait a plusieurs centaines de requetes pour une seule page.

## Corrections appliquees

### 1. Ajout de headers de diagnostic

Un middleware a ete ajoute dans `core/middleware.py`.

Il ajoute des headers HTTP visibles dans DevTools:

- `X-BioAttend-Duration-ms`: duree totale de la requete;
- `X-BioAttend-DB-Queries`: nombre de requetes SQL executees;
- `X-BioAttend-DB-ms`: temps passe dans la base de donnees.

Ces headers permettent de diagnostiquer une page lente sans acces direct a
CapRover ou aux logs serveur.

### 2. Ajout d'indexes PostgreSQL

Des indexes ont ete ajoutes sur les tables les plus sollicitees:

- `pointage`;
- `alerte`;
- `schedule_request`.

Ils ciblent les filtres frequents:

- utilisateur;
- statut;
- type;
- date de pointage;
- origine pointeuse;
- type d'incident;
- demandes planning approuvees sur une periode.

Les migrations ajoutees appliquent ces indexes automatiquement au prochain
deploiement, car le Dockerfile lance deja:

```bash
python manage.py migrate --noinput
```

### 3. Reduction des requetes repetees sur les pointages

La fonction `attach_schedule_display()` etait appelee sur les listes de
pointages, notamment sur la page statistiques.

Avant correction, elle recalculait les informations de planning pointage par
pointage, ce qui declenchait beaucoup de requetes DB.

La correction consiste a charger les donnees necessaires en lot:

- les utilisateurs concernes;
- les jours concernes;
- les demandes planning approuvees sur la periode;
- les pointages valides sur la periode.

Ensuite, les calculs sont faits en memoire Python au lieu de refaire une
requete SQL pour chaque ligne.

L'objectif est de garder les memes informations affichees sur la plateforme,
mais avec beaucoup moins de requetes SQL.

### 4. Optimisation de la page planning

La page planning a ensuite ete mesuree a environ 4,1 secondes:

- `X-BioAttend-Duration-ms`: 4157.7 ms
- `X-BioAttend-DB-Queries`: 116 requetes
- `X-BioAttend-DB-ms`: 3573.6 ms

La page declenchait une synchronisation d'alertes planning pendant un simple
affichage. Cette synchronisation pouvait analyser une periode trop large et
multiplier les requetes `Pointage` et `ScheduleRequest`.

La correction consiste a:

- ne plus recalculer tout le mois a chaque ouverture de la page planning;
- synchroniser uniquement la fenetre recente deja prevue par le service;
- eviter de relancer cette synchronisation a chaque refresh grace a un cache
  court de 15 minutes;
- transformer les listes `pending_requests` et `recent_requests` en listes
  Python avant le rendu pour eviter plusieurs evaluations SQL dans le template.

Le calendrier, les demandes en attente, l'historique recent, les jours feries
et les exports restent disponibles.

Mesures apres deploiement:

- premier chargement:
  - `X-BioAttend-Duration-ms`: 2866.7 ms
  - `X-BioAttend-DB-Queries`: 81 requetes
  - `X-BioAttend-DB-ms`: 2443.1 ms
- deuxieme chargement:
  - `X-BioAttend-Duration-ms`: 1292.1 ms
  - `X-BioAttend-DB-Queries`: 39 requetes
  - `X-BioAttend-DB-ms`: 1139.5 ms

La deuxieme mesure confirme que le cache court evite de refaire la
synchronisation planning a chaque ouverture de page.

### 5. Optimisation du dashboard

Le dashboard a ensuite ete mesure a environ 6,9 secondes:

- `X-BioAttend-Duration-ms`: 6932.6 ms
- `X-BioAttend-DB-Queries`: 212 requetes
- `X-BioAttend-DB-ms`: 6294.2 ms

Le dashboard recalculait les analyses de presence, absence et ponctualite pour
chaque employe et chaque jour de la semaine. Chaque analyse pouvait declencher
des requetes separees vers `Pointage` et `ScheduleRequest`.

La correction ajoute un chargement groupe des analyses planning:

- recuperation en une fois des demandes planning approuvees sur la periode;
- recuperation en une fois des pointages valides sur la periode;
- calcul en memoire des absences, retards, departs anticipes et journees
  courtes;
- reutilisation du meme resultat pour les statistiques hebdomadaires et les
  compteurs du jour.

Les cartes du dashboard, le graphique hebdomadaire et les listes de presence
gardent les memes donnees, mais avec beaucoup moins d'allers-retours SQL.

## Bilan des mesures

### Page statistiques

Mesure avant correction:

- `X-BioAttend-Duration-ms`: 20685.1 ms
- `X-BioAttend-DB-Queries`: 596 requetes
- `X-BioAttend-DB-ms`: 17532.3 ms

Mesure apres correction:

- `X-BioAttend-Duration-ms`: 2023.7 ms
- `X-BioAttend-DB-Queries`: 44 requetes
- `X-BioAttend-DB-ms`: 1506.6 ms

Bilan:

- temps total divise par environ 10;
- requetes DB reduites de 596 a 44;
- temps DB reduit de 17,5 secondes a 1,5 seconde;
- la page reste complete: pointages, historiques, graphiques, alertes et exports.

### Dashboard

Mesure avant correction:

- `X-BioAttend-Duration-ms`: 6932.6 ms
- `X-BioAttend-DB-Queries`: 212 requetes
- `X-BioAttend-DB-ms`: 6294.2 ms

Mesure apres correction:

- `X-BioAttend-Duration-ms`: 1786.2 ms
- `X-BioAttend-DB-Queries`: 49 requetes
- `X-BioAttend-DB-ms`: 1513.6 ms

Bilan:

- temps total reduit de 6,9 secondes a 1,8 seconde;
- requetes DB reduites de 212 a 49;
- le calcul des presences, absences et retards est conserve;
- les donnees hebdomadaires sont calculees en memoire apres chargement groupe.

### Planning

Mesure avant correction:

- `X-BioAttend-Duration-ms`: 4157.7 ms
- `X-BioAttend-DB-Queries`: 116 requetes
- `X-BioAttend-DB-ms`: 3573.6 ms

Mesure apres correction, premier chargement:

- `X-BioAttend-Duration-ms`: 2866.7 ms
- `X-BioAttend-DB-Queries`: 81 requetes
- `X-BioAttend-DB-ms`: 2443.1 ms

Mesure apres correction, deuxieme chargement:

- `X-BioAttend-Duration-ms`: 1292.1 ms
- `X-BioAttend-DB-Queries`: 39 requetes
- `X-BioAttend-DB-ms`: 1139.5 ms

Bilan:

- la premiere ouverture reste plus couteuse car elle peut declencher une
  synchronisation planning;
- le cache court evite de refaire cette synchronisation a chaque refresh;
- au deuxieme chargement, le temps total descend a environ 1,3 seconde;
- les demandes en attente, l'historique recent, le calendrier et les exports
  restent disponibles.

### Onglet employe

Mesure observee:

- `X-BioAttend-Duration-ms`: 1280.5 ms
- `X-BioAttend-DB-Queries`: 20 requetes
- `X-BioAttend-DB-ms`: 741.8 ms

Bilan:

- cette page etait deja dans une zone acceptable;
- aucune correction urgente n'a ete appliquee sur cet onglet;
- elle pourra etre optimisee plus tard si les pages principales sont stables.

### Synthese globale

Les gains principaux viennent de la baisse du nombre de requetes SQL:

- statistiques: 596 -> 44 requetes;
- dashboard: 212 -> 49 requetes;
- planning: 116 -> 39 requetes au deuxieme chargement;
- onglet employe: 20 requetes, deja acceptable.

Le probleme initial etait donc bien un ensemble de requetes repetitives vers
Supabase, amplifie par la latence entre Hetzner Allemagne et Supabase Irlande.

## Ce qui n'a pas ete supprime

La correction ne supprime pas les donnees utiles de la plateforme.

Les elements suivants restent disponibles:

- les pointages;
- les historiques;
- les statistiques;
- les heures prestees;
- les graphiques;
- les alertes;
- les filtres;
- les exports CSV;
- les informations de ponctualite.

## Verification

Les verifications Django ont ete lancees:

```bash
python manage.py check
```

Resultat:

```text
System check identified no issues.
```

Des tests ciblant les modules concernes ont aussi ete lances:

```bash
python manage.py test dashboard Employee schedule api --keepdb
```

## Comment verifier en production

Apres deploiement, ouvrir DevTools dans le navigateur:

1. Ouvrir le site BioAttend.
2. Appuyer sur `F12`.
3. Aller dans l'onglet `Network` / `Reseau`.
4. Recharger la page.
5. Cliquer sur la requete principale, par exemple `/dashboard/` ou la page statistiques.
6. Aller dans `Headers` / `En-tetes`.
7. Lire les headers:
   - `X-BioAttend-Duration-ms`
   - `X-BioAttend-DB-Queries`
   - `X-BioAttend-DB-ms`

Une page corrigee doit avoir beaucoup moins de requetes DB que les 596 mesurees
au depart.

## Recommandations restantes

Pour de meilleures performances a long terme:

- placer l'application et Supabase dans la meme region si possible;
- eviter les recalculs de planning dans les listes longues;
- ajouter une vraie pagination partout ou des historiques complets sont affiches;
- remplacer la creation automatique de l'admin dans `accounts/apps.py` par une
  commande `manage.py`, car cette logique fait une requete DB au demarrage;
- garder les headers de diagnostic le temps de stabiliser les performances.
