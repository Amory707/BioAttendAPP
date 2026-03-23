# BioAttend - Système de Gestion des Absences 🎓

Base HTML/CSS/JS responsive et propre pour votre projet Django.

## 📋 Fichiers Inclus

- **dashboard.html** - HTML principal (version pure, sans tags Django)
- **dashboard_template.html** - Template Django (avec `{% load static %}`)
- **style.css** - Styles responsifs et modernes
- **app.js** - Logique JavaScript (navigation, graphiques, données de test)
- **INTEGRATION_GUIDE.md** - Guide d'intégration avec Django

## ⚡ Installation Rapide

### 1. Copier les fichiers

```bash
# Créer la structure
mkdir -p mon_app/templates/attendance
mkdir -p mon_app/static/css
mkdir -p mon_app/static/js

# Copier les fichiers
cp dashboard_template.html mon_app/templates/attendance/dashboard.html
cp style.css mon_app/static/css/
cp app.js mon_app/static/js/
```

### 2. Configuration Django

Dans `settings.py` :

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'mon_app',  # Votre app
]

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'mon_app' / 'static',
]
```

### 3. URLs

Dans `urls.py` :

```python
from django.contrib import admin
from django.urls import path
from mon_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout, name='logout'),
]
```

### 4. Views

Dans `views.py` :

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import redirect

@login_required(login_url='login')
def dashboard(request):
    return render(request, 'attendance/dashboard.html')

def logout(request):
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return redirect('login')  # À adapter
```

### 5. Collectez les statiques

```bash
python manage.py collectstatic --noinput
```

## 🎨 Fonctionnalités

### ✅ Responsive Design
- Mobile first
- Breakpoints: 1024px, 768px, 480px
- Navigation adaptative

### ✅ Navigation
- 5 pages principales (Dashboard, Employés, Statistiques, Alertes, Paramètres)
- Menu utilisateur avec dropdown
- Navigation fluide avec animations

### ✅ Graphiques
- Chart.js intégré
- 4 types de graphiques:
  - Graphique à barres (semaine)
  - Graphique linéaire (mensuel)
  - Graphique en doughnut (distribution)
  - Données de test JSON incluses

### ✅ Dark Mode
- Toggle dans les paramètres
- Sauvegardé en localStorage
- CSS variables pour adaptation facile

### ✅ Sécurité
- Dropdown menu pour logout
- Détection de clics extérieurs
- Intégration CSRF Django ready

## 🎯 Données de Test

Les données de test sont définies dans `testData` dans `app.js` :

```javascript
const testData = {
    weeklyStats: [...],      // Stats de la semaine
    monthlyStats: [...],     // Stats mensuelles
    recentCheckIns: [...],   // Enregistrements récents
    employees: [...]         // Liste des employés
}
```

Remplacez-les par des appels API une fois prêt :

```javascript
async function loadWeeklyStats() {
    const response = await fetch('/api/weekly-stats/');
    return await response.json();
}
```

## 🔧 Personnalisation

### Changer les Couleurs

Modifiez les variables CSS dans `style.css` (ligne 1-20) :

```css
:root {
    --color-primary: #4A90E2;        /* Bleu principal */
    --color-secondary: #50C878;      /* Vert */
    --color-accent-orange: #FF9F43;  /* Orange */
    /* ... */
}
```

### Ajouter une Page

1. Créer la section HTML:
```html
<section id="ma-page" class="page">
    <div class="page-header"><h1>Ma Page</h1></div>
    <!-- Contenu -->
</section>
```

2. Ajouter le lien nav:
```html
<a href="#" class="nav-item" data-page="ma-page">
    <span class="nav-icon">🎯</span>
    <span class="nav-label">Ma Page</span>
</a>
```

3. Ajouter la logique dans `app.js`:
```javascript
case 'ma-page':
    loadMyPage();
    break;
```

### Changer les Icones

Remplacez les emojis par des icones Font Awesome:

```html
<!-- Remplacer -->
<span class="nav-icon">🏠</span>

<!-- Par -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<span class="nav-icon"><i class="fas fa-home"></i></span>
```

## 📊 Modèles Django Recommandés

```python
from django.db import models
from django.contrib.auth.models import User

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    joined_date = models.DateField(auto_now_add=True)

class Attendance(models.Model):
    ENTRY = 'entry'
    EXIT = 'exit'
    STATUS_CHOICES = [(ENTRY, 'Entrée'), (EXIT, 'Sortie')]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

class Alert(models.Model):
    LEVELS = [('info', 'Info'), ('warning', 'Attention'), ('danger', 'Danger')]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVELS)
    created_at = models.DateTimeField(auto_now_add=True)
```

## 🚀 API Endpoints à Créer

```python
# serializers.py
from rest_framework import serializers
from .models import Attendance, Employee

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'

class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'

# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def api_weekly_stats(request):
    # Retourner les stats de la semaine
    return Response({'weeklyStats': [...]})

@api_view(['GET'])
def api_recent_checkins(request):
    # Retourner les 5 derniers check-ins
    return Response({'recentCheckIns': [...]})
```

## 📱 Responsive Breakpoints

- **Desktop** : > 1024px (Layout 2 colonnes)
- **Tablet** : 768px - 1024px (Layout adapté)
- **Mobile** : < 768px (Layout single column)
- **Small Mobile** : < 480px (Compact)

## 🎓 Points de Développement

- [ ] Connecter les données réelles
- [ ] Implémenter l'authentification
- [ ] Ajouter des permissions (Admin, Manager, User)
- [ ] Créer les API endpoints
- [ ] Tests unitaires
- [ ] Pagination pour les listes
- [ ] Filtres et recherche
- [ ] Export en PDF/Excel
- [ ] WebSockets pour notifications temps réel
- [ ] Notifications email

## 🐛 Troubleshooting

### CSS/JS ne charge pas?
```bash
# Collectez les fichiers statiques
python manage.py collectstatic --noinput

# Vérifiez STATIC_URL dans settings.py
STATIC_URL = '/static/'

# En développement, assurez-vous que DEBUG = True
```

### Graphiques vides?
- Vérifiez que Chart.js est chargé (console F12)
- Vérifiez la hauteur du container (>250px)
- Vérifiez les données JSON dans testData

### Dark mode ne persiste pas?
- localStorage doit être activé
- Vérifiez les paramètres de confidentialité du navigateur

## 📄 Structure CSS

```
style.css
├── Variables CSS
├── Reset et Base
├── Layout Principal
├── Top Bar
├── Pages et Contenu
├── Stats Grid
├── Charts Section
├── Recent Table
├── Responsive Design
└── Animations
```

## 🔐 Sécurité

✅ Protection CSRF Django (ajouté automatiquement)
✅ Authentication requise (`@login_required`)
✅ Pas d'API key en frontend
✅ Validation côté serveur obligatoire
✅ Sanitization des données côté Django

## 📦 Dépendances

- **Chart.js** 4.x (CDN)
- **Django** 3.2+ (Backend)
- Aucune autre dépendance frontend

## 🎨 Design Choices

- **Font** : System fonts (optimisé pour performance)
- **Colors** : Palette cohérente avec gradients
- **Spacing** : CSS variables pour consistency
- **Animations** : Transitions smooth (150-350ms)
- **Shadows** : Hiérarchie visuelle subtile

## 📞 Support

Pour intégrer correctement:
1. Suivre le guide INTEGRATION_GUIDE.md
2. Vérifier que Django et les statiques sont configurés
3. Tester d'abord les données de test
4. Remplacer progressivement par les vraies données

## 📈 Performance

- **First Load** : ~200KB (HTML + CSS)
- **Chart.js** : ~70KB (CDN)
- **Bundle Size** : Minimal (pas de bundler nécessaire)
- **Lighthouse Score** : A (si optimisé)

## 📝 License

Libre d'utilisation pour votre projet scolaire ✓

---

**Créé pour** : Projet Django Scolaire
**Version** : 1.0
**Mise à jour** : Mars 2026
