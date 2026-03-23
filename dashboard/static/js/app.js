// ===========================
// Données de Test JSON
// ===========================
const testData = {
    weeklyStats: [
        { day: 'Mon', presents: 45, absents: 30, unrecorded: 8 },
        { day: 'Tue', presents: 52, absents: 25, unrecorded: 6 },
        { day: 'Wed', presents: 48, absents: 28, unrecorded: 7 },
        { day: 'Thu', presents: 55, absents: 22, unrecorded: 6 },
        { day: 'Fri', presents: 50, absents: 27, unrecorded: 6 },
    ],
    recentCheckIns: [
        { name: 'John', time: '08:01', status: 'entry' },
        { name: 'Maria', time: '08:05', status: 'entry' },
        { name: 'Paul', time: '12:00', status: 'exit' },
        { name: 'Sophie', time: '08:15', status: 'entry' },
        { name: 'Michel', time: '17:30', status: 'exit' },
    ],
};

// ===========================
// Variables Globales
// ===========================
let charts = {};
const colorScheme = {
    primary: '#4A90E2',
    secondary: '#50C878',
    orange: '#FF9F43',
    red: '#EE5A6F',
    blue: '#87CEEB',
    teal: '#1ABC9C',
    gray: '#7F8C8D',
};

// ===========================
// Initialisation
// ===========================
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboard();
    initDarkMode();
});

// ===========================
// Event Listeners
// ===========================
function initializeEventListeners() {
    // Hamburger menu
    const hamburgerMenu = document.getElementById('hamburgerMenu');
    const sidebar = document.getElementById('sidebar');

    if (hamburgerMenu && sidebar) {
        hamburgerMenu.addEventListener('click', () => {
            hamburgerMenu.classList.toggle('active');
            sidebar.classList.toggle('active');
        });

        // Close sidebar when clicking on a nav item
        const navItems = sidebar.querySelectorAll('.nav-item');
        navItems.forEach((item) => {
            item.addEventListener('click', () => {
                hamburgerMenu.classList.remove('active');
                sidebar.classList.remove('active');
            });
        });

        // Close sidebar when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.sidebar') && !e.target.closest('.hamburger-menu')) {
                hamburgerMenu.classList.remove('active');
                sidebar.classList.remove('active');
            }
        });
    }

    // Theme toggle
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // User menu dropdown
    const userMenuBtn = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (userMenuBtn && userDropdown) {
        userMenuBtn.addEventListener('click', () => {
            userDropdown.classList.toggle('active');
            userMenuBtn.classList.toggle('active');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.user-menu-wrapper')) {
                userDropdown.classList.remove('active');
                userMenuBtn.classList.remove('active');
            }
        });
    }

    // Settings link
    const settingsLink = document.getElementById('settingsLink');
    if (settingsLink) {
        settingsLink.addEventListener('click', (e) => {
            e.preventDefault();
            // À adapter selon votre implémentation
            console.log('Paramètres cliqués');
        });
    }
}

// ===========================
// Dashboard
// ===========================
function loadDashboard() {
    loadRecentCheckIns();
    
    // Initialize weekly chart
    setTimeout(() => {
        initWeeklyChart();
    }, 100);
}

function loadRecentCheckIns() {
    const tableBody = document.getElementById('recentTableBody');
    if (!tableBody) return;

    tableBody.innerHTML = testData.recentCheckIns
        .map(
            (item) => `
        <div class="table-row">
            <div class="table-col name-col">${item.name}</div>
            <div class="table-col time-col">${item.time}</div>
            <div class="table-col">
                <span class="status-badge ${item.status}">
                    ${item.status === 'entry' ? 'Entrée' : 'Sortie'}
                </span>
            </div>
        </div>
    `
        )
        .join('');
}

function initWeeklyChart() {
    const ctx = document.getElementById('weeklyChart');
    if (!ctx) return;

    if (charts.weekly) {
        charts.weekly.destroy();
    }

    const isDarkMode = document.body.classList.contains('dark-mode');
    const textColor = isDarkMode ? '#BDC3C7' : '#7F8C8D';

    charts.weekly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: testData.weeklyStats.map((d) => d.day),
            datasets: [
                {
                    label: 'Présents',
                    data: testData.weeklyStats.map((d) => d.presents),
                    backgroundColor: colorScheme.primary,
                    borderRadius: 6,
                    borderSkipped: false,
                },
                {
                    label: 'Absents',
                    data: testData.weeklyStats.map((d) => d.absents),
                    backgroundColor: colorScheme.orange,
                    borderRadius: 6,
                    borderSkipped: false,
                },
                {
                    label: 'Non reconnus',
                    data: testData.weeklyStats.map((d) => d.unrecorded),
                    backgroundColor: colorScheme.gray,
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
                        font: {
                            size: 13,
                            weight: '500',
                        },
                        color: textColor,
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    padding: 12,
                    borderRadius: 8,
                    titleFont: {
                        size: 14,
                        weight: 'bold',
                    },
                    bodyFont: {
                        size: 13,
                    },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                        drawBorder: false,
                    },
                    ticks: {
                        font: {
                            size: 12,
                        },
                        color: textColor,
                    },
                },
                x: {
                    grid: {
                        display: false,
                    },
                    ticks: {
                        font: {
                            size: 12,
                        },
                        color: textColor,
                    },
                },
            },
        },
    });
}

// ===========================
// Theme Management
// ===========================
function toggleTheme() {
    const isDarkMode = document.body.classList.contains('dark-mode');
    
    if (isDarkMode) {
        document.body.classList.remove('dark-mode');
        localStorage.setItem('theme', 'light');
        updateThemeIcon('light');
    } else {
        document.body.classList.add('dark-mode');
        localStorage.setItem('theme', 'dark');
        updateThemeIcon('dark');
    }
    
    // Update chart colors
    if (charts.weekly) {
        initWeeklyChart();
    }
}

function updateThemeIcon(theme) {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        const icon = themeToggleBtn.querySelector('i');
        if (theme === 'dark') {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        }
    }
}

function initDarkMode() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        updateThemeIcon('dark');
    } else {
        document.body.classList.remove('dark-mode');
        updateThemeIcon('light');
    }
}