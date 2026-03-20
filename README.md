# 🧬 BioAttend

Bienvenue sur le projet **BioAttend**. Ce repo est configuré pour être prêt à l'emploi en quelques secondes grâce à GitHub Codespaces.


## 🚀 Démarrage Rapide:

Pour lancer le projet sans te prendre la tête :

1.  **Ouvre le repo** dans un **GitHub Codespace** (Bouton vert `<> Code` > `Codespaces` > `+`).
2.  **Attends 1 minute** : Le container installe automatiquement Python, les dépendances et crée ton fichier `.env`.
3.  **Lance le serveur** :
    ```bash
    python manage.py runserver
    ```
4.  Clique sur le bouton **"Open in Browser"** qui apparaît en bas à droite. Terminé.

## 🛠️ Configuration & Secrets

Le projet utilise **Supabase** pour la base de données et **pgvector** pour la partie IA/Biométrie. 

### Fichier `.env`
Le fichier `.env` est généré automatiquement à l'ouverture du Codespace à partir des **Secrets GitHub**. 
> ⚠️ **Ne modifie pas le `.env` à la main** sauf si tu sais ce que tu fais. Si tu n'as pas accès à la base de données, demande-moi les accès Supabase.

### Dépendances
Si tu installes une nouvelle bibliothèque, n'oublie pas de mettre à jour la liste pour les autres :
```bash
pip freeze > requirements.txt
```

## 📂 Structure du Projet

* `BioAttend/` : Configuration principale (URLs, Settings).
* `manage.py` : Ton couteau suisse pour lancer le serveur, créer des tables, etc.
* `.devcontainer/` : La magie noire qui configure ton environnement automatiquement.
* `requirements.txt` : La liste des ingrédients du projet.

## 💡 Commandes Utiles (Au cas où...)

| Action | Commande |
| :--- | :--- |
| **Créer une table** | `python manage.py makigrations` puis `migrate` |
| **Créer un admin** | `python manage.py createsuperuser` |
| **Installer tout** | `pip install -r requirements.txt` |

## 🧪 Status du projet:

Suivre le Jira svp: [https://nde-code.atlassian.net/jira/software/projects/BIOAT/summary](https://nde-code.atlassian.net/jira/software/projects/BIOAT/summary)

**Développé avec ❤️ pour BioAttend.** Si ça casse, redémarre le Codespace avant de m'appeler !