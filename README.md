# 🧬 BioAttend

Bienvenue sur le projet **BioAttend**. Ce repository est configuré pour être prêt à l'emploi en quelques secondes grâce à **GitHub Codespaces**.

## 🚀 Démarrage Rapide

### Via GitHub Codespaces (Recommandé)

1. **Ouvrez le repository** dans un **GitHub Codespace** :
   - Cliquez sur le bouton vert **`<> Code`** en haut à droite
   - Sélectionnez l'onglet **`Codespaces`**
   - Cliquez sur le bouton **`+`** pour créer un nouvel environnement

2. **Patientez ± 1-2 minutes** : Le conteneur installe automatiquement :
   - Python et ses dépendances
   - Toutes les bibliothèques du projet
   - Votre fichier `.env` personnalisé

3. **Lancez le serveur Django** :
   ```bash
   python manage.py runserver
   ```

4. **Accédez à l'application** :
   - Un bouton **"Open in Browser"** devrait apparaître en bas à droite
   - Sinon, utilisez la notification "Application running on..." dans le terminal
   - Visitez : `http://localhost:8000`

> 📚 **Documentation officielle** : Consultez [GitHub Codespaces - Getting started](https://docs.github.com/en/codespaces/getting-started/quickstart) pour plus d'informations.

## 🌐 Port Forwarding (Partage entre camarades)

**Normalement, j’ai déjà tout préconfiguré pour que vous n’ayez pas à le faire !**

Maintenant si cela ne va pas: pour partager votre environnement de développement en temps réel avec d'autres membres:

1. **Configurez le port forwarding** dans Codespaces :
   - Allez à l'onglet **"Ports"** (en bas à côté de Terminal)
   - Faites un clic droit sur le port `8000`
   - Sélectionnez **"Port Visibility"** → **"Public"**

2. **Partagez l'URL publique** :
   - L'URL générée apparaît sous le port forwarded
   - Exemple : `https://username-bioattend-xxxxx.app.github.dev`
   - Partagez-la avec vos camarades via Slack/Discord

> ⚠️ **Sécurité** : Les ports publics sont exposés sur Internet. Limitez l'accès aux seuls membres de l'équipe et évitez de partager des données sensibles via ces URLs publiques.

## 🛠️ Configuration & Secrets

Le projet utilise :
- **Supabase** pour la base de données PostgreSQL
- **pgvector** pour les embeddings IA/Biométrie

### Fichier `.env`

Le fichier `.env` est **généré automatiquement** à chaque ouverture du Codespace à partir des **GitHub Secrets**.

```
⚠️  NE MODIFIEZ PAS LE `.env` À LA MAIN
```

**Si vous n'avez pas accès à la base de données Supabase :**
- Demandez les accès au responsable du projet
- Il faut avoir les variables de secret correctes dans les GitHub Secrets du repository

### Structure automatisée : `.devcontainer.json`

Au lieu d'un dossier `.devcontainer/`, ce projet utilise un fichier `devcontainer.json` **à la racine du projet** qui :
- Configure l'environnement Python automatiquement
- Installe les dépendances du `requirements.txt`
- Crée le fichier `.env` via les GitHub Secrets
- Lance le serveur au démarrage (optionnel)

Vous n'avez rien à faire — tout est automatisé ! 🎉

### Gestion des dépendances

Si vous installez une nouvelle bibliothèque Python, **mettez à jour la liste pour les autres** :

```bash
pip freeze > requirements.txt
```

Puis commitez le fichier mis à jour.

## 📂 Structure du Projet

```
BioAttend/
├── .github/                # Le fichier pour configurer les actions GitHub ainsi que Dependabot
├── BioAttend/              # Configuration Django principale (settings, urls, wsgi)
├── manage.py               # Interface en ligne de commande Django
├── .devcontainer.json      # Configuration automatique Codespaces (ne pas modifier)
├── requirements.txt        # Dépendances Python
├── .env                    # Modèle de variables d'environnement (fourni)
```

## 🛠️ Ajouter une nouvelle Application Django

Si vous devez créer un nouveau module (ex: `stats`, `notifications`), suivez ces étapes pour que tout soit bien configuré :

1. **Générez l'application** dans le terminal :
   ```bash
   python manage.py startapp nom_de_votre_app
   ```

2. **Enregistrez l'application** :
   Ouvrez `BioAttend/settings.py` et ajoutez le nom de votre app dans la liste `INSTALLED_APPS` :
   ```python
   INSTALLED_APPS = [
       ...
       'pgvector',
       'core',
       'nom_de_votre_app', # Ajoutez votre app ici
   ]
   ```

3. **Préparez la base de données** :
   Si vous créez des modèles (tables) dans `models.py`, n'oubliez pas de synchroniser Supabase :
   ```bash
   python manage.py makemigrations nom_de_votre_app
   python manage.py migrate
   ```

> 💡 **Règle d'or** : Gardez vos applications à la racine du projet (au même niveau que `manage.py`) pour que les imports restent simples.

## 💡 Commandes Utiles

| Action | Commande |
|:-------|:---------|
| **Créer les migrations de base** | `python manage.py makemigrations` |
| **Appliquer les migrations** | `python manage.py migrate` |
| **Créer un super-utilisateur** (admin) | `python manage.py createsuperuser` |
| **Installer toutes les dépendances** | `pip install -r requirements.txt` |

| **Lancer les tests** | `python manage.py test` |
| **Vider la base de données** | `python manage.py migrate zero` (ou supprimer le volume) |

> 💡 **Astuce** : Si quelque chose fonctionne mal, redémarrez le Codespace (bouton `⋯` en haut à gauche → "Rebuild Container") avant de nous contacter.

## 🔐 Sécurité & Secrets

### ⚠️  Avertissement Important sur les Secrets

**Ne commitez JAMAIS de secrets (clés API, tokens, mots de passe) dans le repository !**

Les secrets (clés Supabase, API tokens, etc.) sont :
- Stockés **uniquement** dans les **GitHub Secrets** du repository
- Injectés automatiquement via `.devcontainer.json` dans votre `.env`
- **Jamais visibles** dans le code ou l'historique Git

**Si vous exposez accidentellement un secret :**
1. **Allez immédiatement** dans les **GitHub Secrets**
2. **Régénérez** la clé compromise (dans Supabase ou le service concerné)
3. **Mettez à jour** le GitHub Secret avec la nouvelle valeur
4. **Redémarrez** votre Codespace

### 🛡️  GitGuardian

Ce repository est **surveillé par GitGuardian** — un outil qui détecte automatiquement les secrets exposés.

- **Les commits contenant des secrets sont bloqués** avant d'être pushés
- En cas de détection accidentelle, vous recevrez une **alerte GitHub**
- Consultez l'onglet **"Security"** du repository pour les rapports

> 📖 Plus d'infos : [GitGuardian Documentation](https://docs.gitguardian.com)

## 🧪 Suivi du Projet

Consultez le tableau Jira pour suivre l'avancement :

🔗 **[Jira - BioAttend Project](https://nde-code.atlassian.net/jira/software/projects/BIOAT/summary)**

## 🤝 Besoin d'aide ?

- **Problèmes avec Codespaces ?** → Redémarrez le conteneur (Rebuild)
- **Accès Supabase manquant ?** → Demandez les secrets au responsable
- **Secrets exposés accidentellement ?** → Signalez immédiatement et régénérez la clé
- **Autre problème ?** → Ouvrez une issue GitHub ou contactez directement


**Développé avec ❤️ pour BioAttend.**

Bon codage ! 🚀



