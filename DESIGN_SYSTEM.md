# 📐 BioAttend Design System
## Guide de cohérence visuelle

### 🎨 Système de couleurs
- **Primaire**: `#4A90E2` (Bleu) - Actions principales
- **Succès**: `#10B981` (Vert) - Actions positives  
- **Danger**: `#EF4444` (Rouge) - Destructions, erreurs
- **Warning**: `#F59E0B` (Orange) - Avertissements
- **Info**: `#06B6D4` (Cyan) - Informations

### 🔘 Boutons - Classes à utiliser

```html
<!-- Primary Button (Actions principales) -->
<a href="#" class="btn btn-primary">Action principale</a>
<button class="btn btn-primary">Valider</button>

<!-- Secondary Button (Actions secondaires) -->
<button class="btn btn-secondary">Annuler</button>

<!-- Success Button (Succès) -->
<button class="btn btn-success">Valider</button>

<!-- Danger Button (Suppression) -->
<button class="btn btn-danger">Supprimer</button>

<!-- Export Button (Export) -->
<button class="btn btn-export">Exporter CSV</button>

<!-- Small variant -->
<button class="btn btn-primary btn-small">Petit bouton</button>

<!-- Large variant -->
<button class="btn btn-primary btn-large">Grand bouton</button>
```

### 📊 Cartes et Panels

```html
<!-- Card simple -->
<div class="card">
    <div class="card-header">
        <h3 class="card-title">Titre de la carte</h3>
        <p class="card-subtitle">Sous-titre optionnel</p>
    </div>
    <div class="card-body">
        Contenu de la carte
    </div>
</div>

<!-- Stat Card -->
<div class="stat-card stat-primary">
    <div class="stat-header">
        <h4 class="stat-title">Total Pointages</h4>
        <i class="fas fa-fingerprint stat-icon"></i>
    </div>
    <div class="stat-value">324</div>
    <div class="stat-meta">Entrées + sorties</div>
</div>
```

### 🏷️ Badges et Status

```html
<!-- Badges -->
<span class="badge badge-primary">Info</span>
<span class="badge badge-success">Succès</span>
<span class="badge badge-danger">Danger</span>

<!-- Status Badges -->
<span class="status-badge entry">Entrée</span>
<span class="status-badge exit">Sortie</span>
<span class="status-badge success">Validé</span>
<span class="status-badge danger">Erreur</span>

<!-- Chips -->
<span class="chip">Label</span>
<span class="chip chip-success">Succès</span>
<span class="chip chip-danger">Danger</span>
```

### ⚠️ Alertes

```html
<!-- Alert Success -->
<div class="alert alert-success">
    <i class="fas fa-check-circle"></i> Opération réussie
</div>

<!-- Alert Warning -->
<div class="alert alert-warning">
    <i class="fas fa-exclamation-triangle"></i> Attention
</div>

<!-- Alert Danger -->
<div class="alert alert-danger">
    <i class="fas fa-times-circle"></i> Erreur
</div>
```

### 📐 Espaces et Padding
- `--spacing-xs`: 4px (très petit)
- `--spacing-sm`: 8px (petits éléments)
- `--spacing-md`: 16px (standard)
- `--spacing-lg`: 24px (sections)
- `--spacing-xl`: 32px (grands blocs)
- `--spacing-2xl`: 48px (très grands espacements)

### 📝 Typography

```html
<!-- Headings -->
<h1>Titre principal (32px)</h1>
<h2>Titre secondaire (24px)</h2>
<h3>Titre tertiaire (20px)</h3>

<!-- Text variants -->
<p class="text-muted">Texte secondaire</p>
<p class="text-success">Texte succès</p>
<p class="text-danger">Texte danger</p>
```

### 🎯 Règles de cohérence appliquées

1. ✅ **Un seul style par action**: Tous les boutons de suppression = `btn-danger`
2. ✅ **Couleurs signifiantes**: Vert=succès, Rouge=danger, Orange=warning
3. ✅ **Espacements cohérents**: Utiliser les variables CSS, pas de valeurs en dur
4. ✅ **Ombres subtiles**: Utiliser `--shadow-sm`, `--shadow-md` pour de la profondeur
5. ✅ **Transitions fluides**: Tous les éléments interactifs = `--transition-fast`
6. ✅ **Responsive first**: Mobile-first, puis media queries pour desktop
7. ✅ **Accessibilité**: Icônes avec texte, contraste suffisant

### 🚨 À ÉVITER

❌ Styles inline (utiliser les classes)
❌ Couleurs propriétaires (#123456 au lieu de --color-primary)
❌ Espacements en dur (utiliser --spacing-*)
❌ Boutons avec différents designs pour la même action
❌ Ombres personnalisées (utiliser --shadow-*)

### 📦 Charge CSS
1. `design-system.css` - Variables et composants de base
2. `style.css` - Layout global (sidebar, top-bar, etc)
3. `dashboard.css` - Styles spécifiques au dashboard
4. `auth.css` - Styles spécifiques à l'authentification
5. Fichiers additionnels des blocs spécifiques

---
**Dernière mise à jour**: 2026-04-05
**Version**: 1.0
