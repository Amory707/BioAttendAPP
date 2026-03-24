# 📘 Guide d'Utilisation du Template BioAttend

Ce projet utilise l'**héritage de templates Django**. Cela signifie que vous n'avez pas besoin de recopier le code de la barre de navigation ou du menu latéral pour chaque nouvelle page.

## 🏗️ Structure des fichiers
Le design est découpé pour être réutilisable :
* `base.html` : Contient le squelette (Head, Scripts, Structure globale).
* `partials/` : Contient les morceaux fixes (`_sidebar.html` et `_topbar.html`).
* `votre_page.html` : Votre contenu spécifique.

---

## 🚀 Comment créer une nouvelle page ?

Pour créer une nouvelle fonctionnalité (ex: "Liste des Employés"), suivez ces **3 étapes** :

### 1. Créer le fichier HTML
Créez votre fichier dans le dossier `templates/` (ex: `employees.html`).

### 2. Utiliser le squelette (Extends)
Au tout début de votre fichier, ajoutez cette ligne pour importer le design :
```html
{% extends 'base.html' %}
```

### 3. Remplir les blocs de contenu
Vous n'avez qu'à remplir les "trous" prévus dans `base.html` en utilisant des balises `{% block %}`.

```html
{% extends 'base.html' %}

{% block title %} Employés - BioAttend {% endblock %}

{% block content %}
<section class="page active">
    <div class="page-header">
        <h1>Gestion des Employés</h1>
    </div>
    
    <div class="votre-contenu">
        <p>Bienvenue sur la page des employés.</p>
    </div>
</section>
{% endblock %}
```

---

## 🛠️ Blocs disponibles (Customisation)

| Bloc | Usage |
| :--- | :--- |
| `{% block title %}` | Change le texte de l'onglet du navigateur. |
| `{% block content %}` | **Obligatoire**. C'est ici que vous mettez tout votre HTML. |
| `{% block extra_css %}` | Si vous avez besoin d'un fichier CSS spécifique à votre page. |
| `{% block extra_js %}` | Si vous avez besoin d'un script JS spécifique (ex: une alerte). |

---

## 🎨 Styles CSS et Classes
Le projet utilise déjà **FontAwesome** pour les icônes. Pour garder une cohérence visuelle, utilisez les classes CSS existantes :
* `page-header` : Pour les titres de page.
* `stat-card` : Pour les petits blocs de statistiques.
* `btn-primary` : Pour les boutons principaux.

---

## ⚠️ Règles d'or
1. **Ne modifiez pas directement `base.html`** sans en parler à l'équipe, car cela impactera toutes les pages du projet.
2. Si vous voulez ajouter un lien dans le menu de gauche, faites-le dans `partials/_sidebar.html`.
3. Vérifiez toujours que vous fermez bien vos blocs avec `{% endblock %}`.

---

### Une question ?
N'hésite pas à demander si tu as un souci avec l'intégration !
