# 📚 Guide Complet : Étendre et Dynamiser BioAttend

> Ce document explique comment ajouter des fonctionnalités et remplacer les données de test par des vraies données depuis votre base de données Django.

---

## 📖 Table des Matières

1. [Architecture Générale](#architecture-générale)
2. [Ajouter une Nouvelle Page](#ajouter-une-nouvelle-page)
3. [Remplacer les Données de Test](#remplacer-les-données-de-test)
4. [Créer des APIs](#créer-des-apis)
5. [Dynamiser les Graphiques](#dynamiser-les-graphiques)
6. [Bonnes Pratiques](#bonnes-pratiques)
7. [Exemples Complets](#exemples-complets)

---

## Architecture Générale

### 🏗️ Structure du Projet

```
mon_projet/
├── attendance/                    # Application Django
│   ├── templates/
│   │   └── attendance/
│   │       └── dashboard.html     # Template principal
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── app.js
│   ├── models.py                  # Modèles de données
│   ├── views.py                   # Logique backend (APIs)
│   ├── urls.py                    # Configuration des routes
│   └── admin.py
├── manage.py
└── db.sqlite3
```

### 🔄 Flux de Données

```
Base de Données (Django Models)
           ↓
    Django Views/APIs (JSON)
           ↓
    JavaScript fetch() → app.js
           ↓
    Mise à jour du DOM
           ↓
    Affichage à l'utilisateur
```

---

## Ajouter une Nouvelle Page

### Étape 1️⃣ : Ajouter le HTML

Dans `dashboard.html`, ajoutez une nouvelle section :

```html
<!-- Page: Ma Nouvelle Page -->
<section id="ma-page" class="page">
    <div class="page-header">
        <h1>Ma Nouvelle Page</h1>
    </div>

    <div class="content-area">
        <!-- Votre contenu ici -->
        <div id="myContent">
            <!-- Sera rempli par JavaScript -->
        </div>
    </div>
</section>
```

### Étape 2️⃣ : Ajouter le Lien de Navigation

Dans la navigation du sidebar, ajoutez :

```html
<a href="#" class="nav-item">
    <i class="fas fa-icon-name"></i>
    <span class="nav-label">Ma Page</span>
</a>
```

> 💡 **Icones disponibles** : Utilisez [Font Awesome](https://fontawesome.com/search?m=free) (exemple : `fa-chart-pie`, `fa-calendar`, `fa-file`, etc.)

### Étape 3️⃣ : Ajouter la Logique JavaScript

Dans `app.js`, en haut des données de test :

```javascript
// Ajouter à initializeEventListeners() :
const navItems = sidebar.querySelectorAll('.nav-item');
navItems.forEach((item, index) => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const pageName = ['dashboard', 'employees', 'statistics', 'alerts', 'settings'][index];
        loadPage(pageName);
        // Fermer le hamburger sur mobile
        hamburgerMenu.classList.remove('active');
        sidebar.classList.remove('active');
    });
});
```

Puis ajoutez une fonction pour charger votre page :

```javascript
function loadPage(pageName) {
    // Mettre à jour le nav actif
    document.querySelectorAll('.nav-item').forEach((item, i) => {
        item.classList.toggle('active', i === pageIndex);
    });

    // Cacher toutes les pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    // Afficher la bonne page
    const page = document.getElementById(`${pageName}-page`);
    if (page) {
        page.classList.add('active');
    }

    // Charger les données spécifiques
    if (pageName === 'ma-page') {
        loadMyPageData();
    }
}

function loadMyPageData() {
    // Récupérer les données et remplir la page
    fetch('/api/my-data/')
        .then(r => r.json())
        .then(data => {
            document.getElementById('myContent').innerHTML = `
                <p>Voici mes données: ${data.message}</p>
            `;
        })
        .catch(err => console.error('Erreur:', err));
}
```

---

## Remplacer les Données de Test

### 🔴 Avant (Données Statiques)

```javascript
const testData = {
    weeklyStats: [
        { day: 'Mon', presents: 45, absents: 30, unrecorded: 8 },
        { day: 'Tue', presents: 52, absents: 25, unrecorded: 6 },
        // ... données en dur
    ],
};
```

### 🟢 Après (Données Dynamiques)

```javascript
// Option 1 : Charger directement au démarrage
async function loadAllData() {
    try {
        const response = await fetch('/api/dashboard-data/');
        const data = await response.json();
        
        // Utiliser data à la place de testData
        loadRecentCheckIns(data.recentCheckIns);
        initWeeklyChart(data.weeklyStats);
    } catch (error) {
        console.error('Erreur lors du chargement des données:', error);
    }
}

// Appeler au démarrage
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadAllData();  // ← À la place de loadDashboard()
    initDarkMode();
});
```

### 📝 Adapter les Fonctions Existantes

**Avant :**
```javascript
function loadRecentCheckIns() {
    const tableBody = document.getElementById('recentTableBody');
    tableBody.innerHTML = testData.recentCheckIns.map(...).join('');
}
```

**Après :**
```javascript
function loadRecentCheckIns(data) {  // ← Ajouter le paramètre
    const tableBody = document.getElementById('recentTableBody');
    if (!data || !Array.isArray(data)) {
        console.warn('Données invalides:', data);
        return;
    }
    tableBody.innerHTML = data.map(...).join('');  // ← Utiliser data
}
```

**Avant :**
```javascript
function initWeeklyChart() {
    const data = testData.weeklyStats;  // ← Données de test
    // ...
}
```

**Après :**
```javascript
function initWeeklyChart(statsData) {  // ← Passer les données
    if (!statsData) {
        console.warn('Pas de données pour le graphique');
        return;
    }
    const data = statsData;  // ← Utiliser les données passées
    // ... reste du code inchangé
}
```

---

## Créer des APIs

### Backend : Créer les Endpoints

Dans `views.py` de votre app Django :

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.utils import timezone
import json

# ===========================
# APIs Dashboard
# ===========================

@login_required
@require_http_methods(["GET"])
def api_dashboard_data(request):
    """
    Retourne TOUTES les données du dashboard en une seule requête
    Avantage: Moins de requêtes réseau
    """
    today = timezone.now().date()
    start_week = today - timedelta(days=today.weekday())
    
    # Récupérer les données depuis la BD
    from .models import Attendance, Employee
    
    # Stats de la semaine
    weeklyStats = []
    for i in range(5):  # Lun à Ven
        date = start_week + timedelta(days=i)
        day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][i]
        
        presents = Attendance.objects.filter(
            timestamp__date=date,
            status='entry'
        ).values('employee').distinct().count()
        
        total_employees = Employee.objects.count()
        absents = total_employees - presents
        
        weeklyStats.append({
            'day': day_name,
            'presents': presents,
            'absents': absents,
            'unrecorded': 0,
        })
    
    # Enregistrements récents
    recent = Attendance.objects.select_related('employee').order_by('-timestamp')[:5]
    recentCheckIns = [
        {
            'name': att.employee.user.first_name or att.employee.user.username,
            'time': att.timestamp.strftime('%H:%M'),
            'status': att.status,
        }
        for att in recent
    ]
    
    # Stats résumées
    presents_today = Attendance.objects.filter(
        timestamp__date=today,
        status='entry'
    ).values('employee').distinct().count()
    
    total = Employee.objects.count()
    absents_today = total - presents_today
    
    return JsonResponse({
        'weeklyStats': weeklyStats,
        'recentCheckIns': recentCheckIns,
        'stats': {
            'totalEmployees': total,
            'presentToday': presents_today,
            'absentToday': absents_today,
            'unrecordedToday': 0,
        },
        'success': True,
    })


@login_required
@require_http_methods(["GET"])
def api_weekly_stats(request):
    """API séparée pour les stats de la semaine"""
    # Même logique que ci-dessus mais juste pour weeklyStats
    # ...
    return JsonResponse({'weeklyStats': weeklyStats})


@login_required
@require_http_methods(["GET"])
def api_recent_checkins(request):
    """API séparée pour les enregistrements récents"""
    # Même logique que ci-dessus mais juste pour recentCheckIns
    # ...
    return JsonResponse({'recentCheckIns': recentCheckIns})
```

### Configuration des URLs

Dans `urls.py` :

```python
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Pages
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # APIs
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard'),
    path('api/weekly-stats/', views.api_weekly_stats, name='api_weekly_stats'),
    path('api/recent-checkins/', views.api_recent_checkins, name='api_recent_checkins'),
]
```

### Frontend : Utiliser l'API

Dans `app.js` :

```javascript
// Appeler l'API au chargement
async function loadDashboardData() {
    try {
        const response = await fetch('/attendance/api/dashboard-data/');
        if (!response.ok) throw new Error('Erreur réseau');
        
        const data = await response.json();
        
        if (data.success) {
            // Mettre à jour toutes les données
            loadRecentCheckIns(data.recentCheckIns);
            initWeeklyChart(data.weeklyStats);
            updateStatsCards(data.stats);
        }
    } catch (error) {
        console.error('Erreur lors du chargement:', error);
        // Afficher un message d'erreur à l'utilisateur
        showErrorNotification('Impossible de charger les données');
    }
}

function updateStatsCards(stats) {
    // Mettre à jour les 4 cartes de stats
    document.querySelector('.total-employees .stat-value').textContent = stats.totalEmployees;
    document.querySelector('.present-today .stat-value').textContent = stats.presentToday;
    document.querySelector('.absent-today .stat-value').textContent = stats.absentToday;
    document.querySelector('.not-recorded .stat-value').textContent = stats.unrecordedToday;
}

function showErrorNotification(message) {
    // Créer une notification d'erreur
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.remove(), 5000);
}
```

---

## Dynamiser les Graphiques

### Approche Simple : Passer les Données

```javascript
// AVANT: Les données sont en dur dans la fonction
function initWeeklyChart() {
    const data = testData.weeklyStats;
    // ...
}

// APRÈS: Les données sont passées en paramètre
function initWeeklyChart(weeklyStatsData) {
    // Utiliser weeklyStatsData à la place de testData.weeklyStats
    const labels = weeklyStatsData.map(d => d.day);
    const presentsData = weeklyStatsData.map(d => d.presents);
    const absentsData = weeklyStatsData.map(d => d.absents);
    
    const ctx = document.getElementById('weeklyChart');
    if (charts.weekly) charts.weekly.destroy();
    
    charts.weekly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Présents',
                    data: presentsData,
                    backgroundColor: colorScheme.primary,
                    borderRadius: 6,
                    borderSkipped: false,
                },
                // ... autres datasets
            ],
        },
        // ... options
    });
}
```

### Approche Avancée : Mise à Jour en Temps Réel

```javascript
// Rafraîchir les graphiques tous les 30 secondes
function startAutoRefresh() {
    setInterval(async () => {
        console.log('Rafraîchissement automatique...');
        
        try {
            const response = await fetch('/attendance/api/dashboard-data/');
            const data = await response.json();
            
            // Mettre à jour les graphiques
            initWeeklyChart(data.weeklyStats);
            loadRecentCheckIns(data.recentCheckIns);
            updateStatsCards(data.stats);
        } catch (error) {
            console.error('Erreur lors du rafraîchissement:', error);
        }
    }, 30000);  // 30 secondes
}

// Lancer au démarrage
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboardData();
    startAutoRefresh();  // ← Ajouter ceci
    initDarkMode();
});
```

### Exemple : Ajouter un Graphique de Distribution

```javascript
// Dans le HTML, ajouter:
<div id="absence-distribution" class="chart-card">
    <h3>Distribution des Absences</h3>
    <canvas id="distributionChart"></canvas>
</div>

// Dans app.js:
function initDistributionChart(data) {
    const ctx = document.getElementById('distributionChart');
    if (charts.distribution) charts.distribution.destroy();
    
    // Préparer les données
    const categories = data.map(d => d.category);  // ['Maladie', 'Congé', 'Autre']
    const counts = data.map(d => d.count);
    
    charts.distribution = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories,
            datasets: [{
                data: counts,
                backgroundColor: [
                    colorScheme.primary,
                    colorScheme.orange,
                    colorScheme.gray,
                ],
                borderColor: '#fff',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { padding: 20, font: { size: 13, weight: '500' } },
                },
            },
        },
    });
}

// Appeler avec les données
async function loadDashboardData() {
    // ... code existant ...
    const response = await fetch('/attendance/api/dashboard-data/');
    const data = await response.json();
    
    loadRecentCheckIns(data.recentCheckIns);
    initWeeklyChart(data.weeklyStats);
    initDistributionChart(data.distributionData);  // ← Ajouter
    updateStatsCards(data.stats);
}
```

---

## Bonnes Pratiques

### ✅ Faire

- **Toujours passer les données en paramètres** aux fonctions
- **Utiliser `try/catch`** pour les requêtes fetch
- **Valider les données** avant de les afficher
- **Afficher un loading** pendant le chargement des données
- **Cacher les données de test** quand l'API fonctionne
- **Documenter vos APIs** avec des commentaires
- **Tester localement** avant de merger

### ❌ Ne pas Faire

- Ne pas laisser les données en dur dans le JavaScript
- Ne pas oublier `@login_required` sur les vues sensibles
- Ne pas faire confiance aux données du client
- Ne pas multiplier les requêtes API (regrouper si possible)
- Ne pas oublier de traiter les erreurs réseau

---

## Exemples Complets

### Exemple 1 : Ajouter une Table d'Employés

**HTML :**
```html
<section id="employees-page" class="page">
    <div class="page-header">
        <h1>Employés</h1>
    </div>
    <div class="employees-table">
        <table id="employeesTableBody">
            <thead>
                <tr><th>Nom</th><th>Email</th><th>Département</th></tr>
            </thead>
            <tbody id="employeesRows">
                <!-- Rempli par JS -->
            </tbody>
        </table>
    </div>
</section>
```

**Python (views.py) :**
```python
@login_required
def api_employees(request):
    from .models import Employee
    
    employees = Employee.objects.select_related('user').values(
        'id',
        'user__first_name',
        'user__last_name',
        'user__email',
        'department'
    )
    
    return JsonResponse({
        'employees': [
            {
                'id': emp['id'],
                'name': f"{emp['user__first_name']} {emp['user__last_name']}",
                'email': emp['user__email'],
                'department': emp['department'],
            }
            for emp in employees
        ]
    })
```

**JavaScript (app.js) :**
```javascript
function loadEmployeesPage() {
    fetch('/attendance/api/employees/')
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById('employeesRows');
            tbody.innerHTML = data.employees.map(emp => `
                <tr>
                    <td>${emp.name}</td>
                    <td>${emp.email}</td>
                    <td>${emp.department}</td>
                </tr>
            `).join('');
        })
        .catch(err => console.error('Erreur:', err));
}
```

### Exemple 2 : Ajouter un Filtre par Date

**HTML :**
```html
<div class="filter-container">
    <input type="date" id="dateFilter">
    <button id="applyFilterBtn">Appliquer</button>
</div>
<div id="filteredResults"></div>
```

**JavaScript :**
```javascript
document.getElementById('applyFilterBtn').addEventListener('click', () => {
    const date = document.getElementById('dateFilter').value;
    
    fetch(`/attendance/api/attendance-by-date/?date=${date}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('filteredResults').innerHTML = `
                <p>Résultats pour ${date}: ${data.count} enregistrements</p>
            `;
        });
});
```

**Python (views.py) :**
```python
@login_required
def api_attendance_by_date(request):
    date = request.GET.get('date')
    
    from datetime import datetime
    from .models import Attendance
    
    try:
        parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        count = Attendance.objects.filter(timestamp__date=parsed_date).count()
        
        return JsonResponse({'count': count, 'date': date})
    except ValueError:
        return JsonResponse({'error': 'Format de date invalide'}, status=400)
```

### Exemple 3 : Export en CSV/PDF

**JavaScript :**
```javascript
document.getElementById('exportBtn').addEventListener('click', () => {
    const format = prompt('PDF ou CSV?').toLowerCase();
    window.location.href = `/attendance/api/export-report/?format=${format}`;
});
```

**Python (views.py) :**
```python
@login_required
def api_export_report(request):
    import csv
    from django.http import HttpResponse
    
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'csv':
        from .models import Attendance
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="absences.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Employé', 'Date', 'Statut'])
        
        for att in Attendance.objects.all():
            writer.writerow([
                att.employee.user.get_full_name(),
                att.timestamp.date(),
                att.status,
            ])
        
        return response
    
    # Pour PDF, utiliser reportlab ou django-weasyprint
    return JsonResponse({'error': 'PDF non implémenté'})
```

---

## Checklist d'Implémentation

### Phase 1 : Backend (Django)

- [ ] Créer les modèles (`models.py`)
- [ ] Créer les migrations (`makemigrations`, `migrate`)
- [ ] Créer les vues/APIs (`views.py`)
- [ ] Configurer les URLs (`urls.py`)
- [ ] Tester avec Postman ou `curl`

### Phase 2 : Frontend (JavaScript)

- [ ] Mettre à jour `app.js` pour utiliser les APIs
- [ ] Remplacer les `testData`
- [ ] Tester dans le navigateur (F12 → Network)
- [ ] Vérifier les erreurs dans la console

### Phase 3 : Optimisation

- [ ] Ajouter le cache (localStorage)
- [ ] Mettre en place l'auto-refresh
- [ ] Ajouter les notifications d'erreur
- [ ] Tester sur mobile

---

## Debugging

### Problèmes Courants

#### 1. "La requête échoue (404, 500)"

**Solution :**
```javascript
fetch('/attendance/api/dashboard-data/')
    .then(r => {
        console.log('Status:', r.status);  // ← Affiche le code HTTP
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    })
    .catch(err => console.error('Erreur réseau:', err));
```

#### 2. "Les données ne s'affichent pas"

**Vérifier :**
```javascript
function loadRecentCheckIns(data) {
    console.log('Données reçues:', data);  // ← Afficher les données
    
    if (!data || !Array.isArray(data)) {
        console.error('Format incorrect:', data);
        return;
    }
    // ...
}
```

#### 3. "Le graphique ne se met pas à jour"

**Vérifier :**
```javascript
function initWeeklyChart(data) {
    console.log('Données graphique:', data);  // ← Afficher
    
    // Détruire l'ancien graphique
    if (charts.weekly) {
        console.log('Destruction ancien graphique');
        charts.weekly.destroy();
    }
    
    // Créer le nouveau
    charts.weekly = new Chart(...);
}
```

### Outils de Debug

```javascript
// 1. Afficher tous les appels API
window.addEventListener('fetch', e => {
    console.log('Fetch:', e.request.url);
});

// 2. Monitorer les changements de DOM
const observer = new MutationObserver(mutations => {
    console.log('DOM changé:', mutations);
});

// 3. Mesurer les performances
performance.mark('start-load');
// ... votre code ...
performance.mark('end-load');
performance.measure('load', 'start-load', 'end-load');
console.log(performance.getEntriesByName('load')[0]);
```

---

## Ressources Utiles

- 📖 [Django Docs - Class-based Views](https://docs.djangoproject.com/en/stable/topics/class-based-views/)
- 📖 [MDN - Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- 📖 [Chart.js Documentation](https://www.chartjs.org/docs/latest/)
- 🛠️ [Postman - API Testing](https://www.postman.com/)
- 🐛 [Browser DevTools](https://developer.chrome.com/docs/devtools/)

---

## Besoin d'Aide ?

### Questions Fréquentes

**Q: Combien de requêtes API dois-je faire ?**
> R: Idéalement, une seule requête qui retourne toutes les données du dashboard. Sinon, regrouppez-les.

**Q: Comment tester l'API sans le frontend ?**
> R: Utilisez Postman ou `curl`:
> ```bash
> curl -H "Cookie: sessionid=..." http://localhost:8000/attendance/api/dashboard-data/
> ```

**Q: Comment mettre à jour les données en temps réel ?**
> R: Utilisez WebSockets (django-channels) ou un polling simple avec `setInterval`.

**Q: Comment gérer les erreurs ?**
> R: Toujours faire `if (!response.ok)` et afficher un message à l'utilisateur.

---

## Conclusion

✨ Vous avez maintenant tous les outils pour :

✅ Ajouter des pages
✅ Créer des APIs
✅ Remplacer les données de test
✅ Dynamiser les graphiques
✅ Debugger vos problèmes

**N'hésitez pas à découper le code en petites fonctions réutilisables !**

Bon codage ! 🚀