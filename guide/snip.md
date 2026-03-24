# 📦 Snippets Réutilisables

> Collection de blocs de code à copier-coller pour implémenter rapidement des fonctionnalités communes.

---

## 🟦 JavaScript Patterns

### Pattern 1 : Charger des Données avec Gestion d'Erreur

```javascript
async function fetchData(endpoint) {
    try {
        const response = await fetch(endpoint);
        
        // Vérifier le statut HTTP
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Vérifier si la réponse est valide
        if (!data || typeof data !== 'object') {
            throw new Error('Format de réponse invalide');
        }
        
        console.log('✅ Données chargées:', data);
        return data;
        
    } catch (error) {
        console.error('❌ Erreur:', error.message);
        showNotification(`Erreur: ${error.message}`, 'error');
        return null;
    }
}

// Utilisation
const data = await fetchData('/api/dashboard-data/');
if (data) {
    // Utiliser les données
}
```

### Pattern 2 : Notifier l'Utilisateur

```javascript
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'error' ? '#f44336' : '#4CAF50'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

// Utilisation
showNotification('✅ Données mises à jour!', 'success');
showNotification('❌ Erreur de connexion', 'error');
showNotification('ℹ️ Veuillez patienter...', 'info');
```

### Pattern 3 : Rafraîchissement Automatique

```javascript
let autoRefreshInterval = null;

function startAutoRefresh(endpoint, updateFunction, interval = 30000) {
    console.log(`🔄 Auto-refresh activé (toutes les ${interval/1000}s)`);
    
    // Charger immédiatement
    updateFunction(endpoint);
    
    // Puis rafraîchir régulièrement
    autoRefreshInterval = setInterval(() => {
        console.log('🔄 Rafraîchissement...');
        updateFunction(endpoint);
    }, interval);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        console.log('⏹️ Auto-refresh arrêté');
    }
}

// Utilisation
async function updateDashboard(endpoint) {
    const data = await fetchData(endpoint);
    if (data) {
        loadRecentCheckIns(data.recentCheckIns);
        initWeeklyChart(data.weeklyStats);
    }
}

startAutoRefresh('/api/dashboard-data/', updateDashboard, 30000);
```

### Pattern 4 : Valider les Données

```javascript
function validateData(data, schema) {
    // schema = { weeklyStats: 'array', stats: 'object' }
    
    for (const [key, expectedType] of Object.entries(schema)) {
        if (!(key in data)) {
            console.warn(`⚠️ Clé manquante: ${key}`);
            return false;
        }
        
        const actualType = Array.isArray(data[key]) ? 'array' : typeof data[key];
        
        if (actualType !== expectedType) {
            console.warn(`⚠️ Type invalide pour ${key}: attendu ${expectedType}, reçu ${actualType}`);
            return false;
        }
    }
    
    return true;
}

// Utilisation
const schema = {
    weeklyStats: 'array',
    recentCheckIns: 'array',
    stats: 'object',
    success: 'boolean',
};

if (validateData(data, schema)) {
    console.log('✅ Données valides');
} else {
    console.error('❌ Données invalides');
}
```

### Pattern 5 : Cache Local

```javascript
class DataCache {
    constructor(storageKey, ttl = 5 * 60 * 1000) {  // 5 minutes par défaut
        this.storageKey = storageKey;
        this.ttl = ttl;
    }
    
    set(data) {
        const cacheData = {
            data: data,
            timestamp: Date.now(),
        };
        localStorage.setItem(this.storageKey, JSON.stringify(cacheData));
        console.log('💾 Données mises en cache');
    }
    
    get() {
        const cached = localStorage.getItem(this.storageKey);
        if (!cached) return null;
        
        const cacheData = JSON.parse(cached);
        const isExpired = Date.now() - cacheData.timestamp > this.ttl;
        
        if (isExpired) {
            console.log('⏰ Cache expiré');
            this.clear();
            return null;
        }
        
        console.log('✅ Données du cache');
        return cacheData.data;
    }
    
    clear() {
        localStorage.removeItem(this.storageKey);
    }
}

// Utilisation
const dashboardCache = new DataCache('dashboard_data', 5 * 60 * 1000);

async function loadDashboardWithCache() {
    // Vérifier le cache d'abord
    let data = dashboardCache.get();
    
    if (!data) {
        // Si pas en cache, faire la requête
        data = await fetchData('/api/dashboard-data/');
        if (data) {
            dashboardCache.set(data);
        }
    }
    
    if (data) {
        loadRecentCheckIns(data.recentCheckIns);
        initWeeklyChart(data.weeklyStats);
    }
}
```

---

## 🐍 Django Patterns

### Pattern 1 : API Générique

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

@login_required
@require_http_methods(["GET"])
def api_generic(request):
    """Template générique pour une API"""
    try:
        # 1. Récupérer les paramètres
        page = request.GET.get('page', 1)
        limit = request.GET.get('limit', 10)
        
        # 2. Valider les paramètres
        try:
            page = int(page)
            limit = int(limit)
        except ValueError:
            return JsonResponse({'error': 'Paramètres invalides'}, status=400)
        
        # 3. Récupérer les données
        # from .models import MyModel
        # items = MyModel.objects.all()
        
        # 4. Paginer
        # from django.core.paginator import Paginator
        # paginator = Paginator(items, limit)
        # page_obj = paginator.get_page(page)
        
        # 5. Serializer
        # serialized_items = [{'id': item.id, 'name': item.name} for item in page_obj]
        
        # 6. Répondre
        return JsonResponse({
            'success': True,
            'data': [],  # serialized_items
            'page': page,
            'total_pages': 1,  # paginator.num_pages
        })
        
    except Exception as e:
        print(f'Erreur: {e}')
        return JsonResponse(
            {'error': 'Erreur serveur'},
            status=500
        )
```

### Pattern 2 : Querysets Optimisés

```python
# ❌ N+1 Problem
attendances = Attendance.objects.all()
for att in attendances:
    print(att.employee.user.first_name)  # ← Requête par item!

# ✅ Optimisé
attendances = Attendance.objects.select_related(
    'employee',      # ForeignKey
    'employee__user'  # Relation imbriquée
).all()

for att in attendances:
    print(att.employee.user.first_name)  # ← Pas de requête supplémentaire
```

### Pattern 3 : Gérer les Permissions

```python
from django.contrib.auth.models import Permission
from django.contrib.auth.decorators import user_passes_test

def is_admin(user):
    return user.is_staff

@user_passes_test(is_admin)
def admin_only_view(request):
    return JsonResponse({'message': 'Admin uniquement'})

# Ou avec des groupes:
from django.contrib.auth.models import Group

def is_manager(user):
    return user.groups.filter(name='Managers').exists()

@user_passes_test(is_manager)
def manager_view(request):
    return JsonResponse({'message': 'Manager ou Admin'})
```

### Pattern 4 : Filtrage Dynamique

```python
from django.db.models import Q
from datetime import datetime, timedelta

def api_search(request):
    """Recherche avec filtres dynamiques"""
    from .models import Attendance
    
    query = Attendance.objects.all()
    
    # Filtre par date
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        query = query.filter(
            timestamp__date__range=[date_from, date_to]
        )
    
    # Filtre par employé
    employee_id = request.GET.get('employee_id')
    if employee_id:
        query = query.filter(employee_id=employee_id)
    
    # Filtre par statut
    status = request.GET.get('status')  # 'entry' ou 'exit'
    if status in ['entry', 'exit']:
        query = query.filter(status=status)
    
    # Recherche textuelle
    search_text = request.GET.get('search')
    if search_text:
        query = query.filter(
            Q(employee__user__first_name__icontains=search_text) |
            Q(employee__user__last_name__icontains=search_text)
        )
    
    # Retourner
    results = list(query.values('id', 'employee__user__first_name', 'timestamp', 'status'))
    
    return JsonResponse({
        'success': True,
        'count': len(results),
        'results': results,
    })
```

### Pattern 5 : Bulkhead / Rate Limiting

```python
from django.core.cache import cache
from django.http import JsonResponse

def api_with_rate_limit(request):
    """API avec rate limiting"""
    user_id = request.user.id
    cache_key = f'api_calls_{user_id}'
    
    # Récupérer le nombre d'appels
    call_count = cache.get(cache_key, 0)
    
    # Limiter à 100 appels par heure
    if call_count >= 100:
        return JsonResponse(
            {'error': 'Trop de requêtes, réessayez dans 1 heure'},
            status=429  # Too Many Requests
        )
    
    # Incrémenter
    cache.set(cache_key, call_count + 1, 3600)  # 1 heure
    
    # Continuer
    return JsonResponse({'success': True})
```

---

## 🎨 CSS Patterns

### Pattern 1 : Loader/Spinner

```css
/* CSS */
.loader {
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-top: 4px solid #4A90E2;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
```

```html
<!-- HTML -->
<div class="loader"></div>
```

### Pattern 2 : Skeleton Loading

```css
.skeleton {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
    background-size: 200% 100%;
    animation: loading 1.5s infinite;
}

@keyframes loading {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
```

```html
<div class="skeleton" style="width: 100px; height: 20px;"></div>
```

### Pattern 3 : Toast Notification

```css
.notification {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 15px 20px;
    background: #333;
    color: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    animation: slideUp 0.3s ease-out;
    z-index: 9999;
}

.notification-success { background: #4CAF50; }
.notification-error { background: #f44336; }
.notification-info { background: #2196F3; }

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

---

## 📊 Chart.js Patterns

### Pattern 1 : Graphique Générique

```javascript
function createChart(canvasId, type, labels, datasets, title) {
    const ctx = document.getElementById(canvasId);
    
    if (charts[canvasId]) {
        charts[canvasId].destroy();
    }
    
    charts[canvasId] = new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                title: { display: !!title, text: title },
            },
            scales: {
                y: { beginAtZero: true },
            },
        },
    });
}

// Utilisation
createChart(
    'myChart',
    'bar',
    ['Jan', 'Feb', 'Mar'],
    [{
        label: 'Sales',
        data: [12, 19, 3],
        backgroundColor: '#4A90E2',
    }],
    'Monthly Sales'
);
```

### Pattern 2 : Graphique Dynamique

```javascript
function updateChartData(chartName, newData) {
    if (!charts[chartName]) return;
    
    // Mettre à jour les données
    charts[chartName].data.datasets[0].data = newData;
    
    // Redessiner
    charts[chartName].update('none');  // 'none' = pas d'animation
}

// Utilisation
updateChartData('weeklyChart', [10, 20, 30, 40, 50]);
```

---

## 🔧 Utilitaires Généraux

### Pattern 1 : Logger avec Timestamp

```javascript
const logger = {
    log: (msg) => console.log(`[${new Date().toLocaleTimeString()}] ${msg}`),
    warn: (msg) => console.warn(`[${new Date().toLocaleTimeString()}] ⚠️ ${msg}`),
    error: (msg) => console.error(`[${new Date().toLocaleTimeString()}] ❌ ${msg}`),
    success: (msg) => console.log(`[${new Date().toLocaleTimeString()}] ✅ ${msg}`),
};

// Utilisation
logger.success('Données chargées');
logger.warn('Données en cache');
logger.error('Erreur réseau');
```

### Pattern 2 : Formater les Données

```javascript
const formatter = {
    date: (date) => new Date(date).toLocaleDateString('fr-FR'),
    time: (date) => new Date(date).toLocaleTimeString('fr-FR'),
    number: (num) => num.toLocaleString('fr-FR'),
    percent: (num) => `${(num * 100).toFixed(2)}%`,
    bytes: (bytes) => {
        const sizes = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        while (bytes >= 1024 && i < sizes.length - 1) {
            bytes /= 1024;
            i++;
        }
        return `${bytes.toFixed(2)} ${sizes[i]}`;
    },
};

// Utilisation
formatter.date('2024-01-15');      // 15/01/2024
formatter.number(1000000);          // 1 000 000
formatter.percent(0.5);             // 50.00%
```

### Pattern 3 : Delay/Sleep

```javascript
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Utilisation
async function doSomethingWithDelay() {
    console.log('Avant');
    await delay(2000);
    console.log('Après 2 secondes');
}
```

---

## 📈 Patterns de Performance

### Pattern 1 : Debounce (Recherche en Temps Réel)

```javascript
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

// Utilisation: Recherche qui ne se lance que 500ms après l'arrêt de la saisie
const handleSearch = debounce((query) => {
    fetch(`/api/search/?q=${query}`)
        .then(r => r.json())
        .then(data => console.log(data));
}, 500);

document.getElementById('searchInput').addEventListener('input', (e) => {
    handleSearch(e.target.value);
});
```

### Pattern 2 : Throttle (Scroll Events)

```javascript
function throttle(func, delay) {
    let lastCall = 0;
    return function(...args) {
        const now = Date.now();
        if (now - lastCall >= delay) {
            func(...args);
            lastCall = now;
        }
    };
}

// Utilisation: Événement scroll limité à 1x par 100ms
window.addEventListener('scroll', throttle(() => {
    console.log('Scrolling...');
}, 100));
```

---

## ✨ Conclusion

Tous ces patterns peuvent être copiés-collés et adaptés à votre besoin !

**Besoin d'un pattern spécifique ? Demandez ! 🚀**