# ⚡ Quick Start : Implémenter les Vraies Données en 5 minutes

> Procédure rapide pour remplacer les données de test par vos vraies données Django.

---

## 🎯 Objectif

Passer de ceci :
```javascript
const testData = { weeklyStats: [...] };  // ❌ Données en dur
```

À ceci :
```javascript
const data = await fetch('/api/dashboard-data/').then(r => r.json());  // ✅ Vraies données
```

---

## 📋 Checklist Rapide (Copier-Coller)

### ✅ Étape 1 : Créer l'API Django (5 min)

**Fichier : `attendance/views.py`**

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.utils import timezone

@login_required
@require_http_methods(["GET"])
def api_dashboard_data(request):
    """API principale du dashboard"""
    today = timezone.now().date()
    start_week = today - timedelta(days=today.weekday())
    
    from .models import Attendance, Employee
    
    # 1. Stats de la semaine
    weeklyStats = []
    for i in range(5):
        date = start_week + timedelta(days=i)
        day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][i]
        
        presents = Attendance.objects.filter(
            timestamp__date=date,
            status='entry'
        ).values('employee').distinct().count()
        
        total = Employee.objects.count()
        
        weeklyStats.append({
            'day': day_name,
            'presents': presents,
            'absents': total - presents,
            'unrecorded': 0,
        })
    
    # 2. Enregistrements récents
    recentCheckIns = []
    for att in Attendance.objects.order_by('-timestamp')[:5]:
        recentCheckIns.append({
            'name': att.employee.user.first_name or att.employee.user.username,
            'time': att.timestamp.strftime('%H:%M'),
            'status': att.status,
        })
    
    # 3. Statistiques résumées
    presents_today = Attendance.objects.filter(
        timestamp__date=today,
        status='entry'
    ).values('employee').distinct().count()
    total_employees = Employee.objects.count()
    
    return JsonResponse({
        'weeklyStats': weeklyStats,
        'recentCheckIns': recentCheckIns,
        'stats': {
            'totalEmployees': total_employees,
            'presentToday': presents_today,
            'absentToday': total_employees - presents_today,
            'unrecordedToday': 0,
        },
        'success': True,
    })
```

### ✅ Étape 2 : Ajouter l'URL

**Fichier : `attendance/urls.py`**

```python
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard'),  # ← AJOUTER
]
```

### ✅ Étape 3 : Mettre à jour app.js

**Fichier : `static/js/app.js`**

Remplacez cette ligne au démarrage :

```javascript
// ❌ AVANT
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboard();  // ← Utilise testData
    initDarkMode();
});
```

Par ceci :

```javascript
// ✅ APRÈS
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadRealData();  // ← Utilise l'API
    initDarkMode();
});

// Nouvelle fonction
async function loadRealData() {
    try {
        const response = await fetch('/attendance/api/dashboard-data/');
        if (!response.ok) throw new Error('Erreur réseau');
        
        const data = await response.json();
        
        if (data.success) {
            loadRecentCheckIns(data.recentCheckIns);
            initWeeklyChart(data.weeklyStats);
            updateStatsCards(data.stats);
        }
    } catch (error) {
        console.error('Erreur:', error);
        // Fallback sur les données de test si erreur
        loadDashboard();
    }
}

// Ajouter cette fonction
function updateStatsCards(stats) {
    document.querySelector('.total-employees .stat-value').textContent = stats.totalEmployees;
    document.querySelector('.present-today .stat-value').textContent = stats.presentToday;
    document.querySelector('.absent-today .stat-value').textContent = stats.absentToday;
    document.querySelector('.not-recorded .stat-value').textContent = stats.unrecordedToday;
}
```

### ✅ Étape 4 : Mettre à jour les fonctions

**Modification 1 : `loadRecentCheckIns()`**

```javascript
// ✅ AVANT (utilise testData)
function loadRecentCheckIns() {
    const tableBody = document.getElementById('recentTableBody');
    tableBody.innerHTML = testData.recentCheckIns.map(...).join('');
}

// ✅ APRÈS (accepte les données en paramètre)
function loadRecentCheckIns(data) {
    const tableBody = document.getElementById('recentTableBody');
    tableBody.innerHTML = data.map((item) => `
        <div class="table-row">
            <div class="table-col name-col">${item.name}</div>
            <div class="table-col time-col">${item.time}</div>
            <div class="table-col">
                <span class="status-badge ${item.status}">
                    ${item.status === 'entry' ? 'Entrée' : 'Sortie'}
                </span>
            </div>
        </div>
    `).join('');
}
```

**Modification 2 : `initWeeklyChart()`**

```javascript
// ✅ AVANT (utilise testData)
function initWeeklyChart() {
    const ctx = document.getElementById('weeklyChart');
    
    charts.weekly = new Chart(ctx, {
        data: {
            labels: testData.weeklyStats.map((d) => d.day),  // ← testData
            datasets: [
                {
                    data: testData.weeklyStats.map((d) => d.presents),  // ← testData
                    // ...
                },
            ],
        },
    });
}

// ✅ APRÈS (utilise les données passées)
function initWeeklyChart(weeklyStatsData) {
    const ctx = document.getElementById('weeklyChart');
    
    if (charts.weekly) charts.weekly.destroy();
    
    charts.weekly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: weeklyStatsData.map((d) => d.day),  // ← weeklyStatsData
            datasets: [
                {
                    label: 'Présents',
                    data: weeklyStatsData.map((d) => d.presents),  // ← weeklyStatsData
                    backgroundColor: colorScheme.primary,
                    borderRadius: 6,
                    borderSkipped: false,
                },
                {
                    label: 'Absents',
                    data: weeklyStatsData.map((d) => d.absents),  // ← weeklyStatsData
                    backgroundColor: colorScheme.orange,
                    borderRadius: 6,
                    borderSkipped: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: { size: 13, weight: '500' },
                    },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.05)', drawBorder: false },
                },
                x: { grid: { display: false } },
            },
        },
    });
}
```

---

## 🧪 Tester

### 1. Vérifier l'API avec cURL

```bash
curl -H "Cookie: sessionid=YOUR_SESSION_ID" http://localhost:8000/attendance/api/dashboard-data/
```

### 2. Vérifier dans le navigateur

- Ouvrir DevTools (F12)
- Aller dans **Network**
- Recharger la page
- Chercher `api/dashboard-data/`
- Vérifier la réponse JSON

### 3. Vérifier dans la console

```javascript
// Dans la console navigateur (F12)
fetch('/attendance/api/dashboard-data/')
    .then(r => r.json())
    .then(data => console.log(data));
```

---

## 🚨 Problèmes Courants

### ❌ Erreur 404 : URL introuvable

**Solution :** Vérifier que l'URL dans `urls.py` est correcte

```python
path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard'),
#    ↑ Doit correspondre au fetch
```

### ❌ Erreur 403 : Forbidden

**Solution :** Vous n'êtes pas connecté. La vue a `@login_required`.

```bash
# Assurez-vous d'être connecté dans le navigateur
# Et que le cookie de session existe
```

### ❌ Erreur 500 : Erreur serveur

**Solution :** Vérifier les logs Django

```bash
python manage.py runserver  # ← Regarder la console
```

### ❌ Les données ne s'affichent pas

**Checker dans la console (F12) :**

```javascript
// Ajouter des logs dans app.js
async function loadRealData() {
    try {
        console.log('Début du chargement...');
        
        const response = await fetch('/attendance/api/dashboard-data/');
        console.log('Response status:', response.status);  // ← Doit être 200
        
        const data = await response.json();
        console.log('Data reçue:', data);  // ← Afficher les données
        
        if (data.success) {
            console.log('Mise à jour du DOM...');
            loadRecentCheckIns(data.recentCheckIns);
            initWeeklyChart(data.weeklyStats);
            updateStatsCards(data.stats);
        }
    } catch (error) {
        console.error('Erreur complète:', error);
        loadDashboard();  // Fallback
    }
}
```

---

## 📝 Points Importants

| ✅ À Faire | ❌ À Éviter |
|-----------|-----------|
| Passer les données en paramètres | Garder testData en dur |
| Ajouter `@login_required` | Oublier la sécurité |
| Valider les données (`if (!data)`) | Supposer les données valides |
| Utiliser `try/catch` | Ignorer les erreurs réseau |
| Tester avec F12 → Network | Tester à l'aveugle |

---

## 📚 Modèles Django Nécessaires

Si vous n'avez pas encore les modèles, créez-les :

**`attendance/models.py`**

```python
from django.db import models
from django.contrib.auth.models import User

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100, default='Default')
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

class Attendance(models.Model):
    ENTRY = 'entry'
    EXIT = 'exit'
    STATUS_CHOICES = [(ENTRY, 'Entrée'), (EXIT, 'Sortie')]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.employee} - {self.status}"
```

Puis :
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## ✨ Prochaines Étapes

Une fois fonctionnel :

1. ✅ **Ajouter d'autres APIs** (employés, alertes, stats mensuelles)
2. ✅ **Ajouter des filtres** (date, département, etc.)
3. ✅ **Auto-refresh** : Rafraîchir les données toutes les 30 secondes
4. ✅ **Notifications** : Afficher les erreurs à l'utilisateur
5. ✅ **WebSockets** : Mises à jour temps réel (avancé)

---

## 🎉 Résumé

Vous avez maintenant :

✅ Une API Django qui retourne les vraies données
✅ Un JavaScript qui appelle l'API
✅ Les graphiques qui se mettent à jour dynamiquement
✅ Une application fonctionnelle et extensible

**C'est tout ce qu'il fallait ! 🚀**

---

**Besoin d'aide ?** Consultez `GUIDE_EXTENSION.md` pour plus de détails.