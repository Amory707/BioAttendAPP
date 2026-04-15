/**
 * DASHBOARD.JS - Logique spécifique au Dashboard
 * Gère : Graphiques Chart.js et tableau des présences
 */
const dashboardCharts = {}; 
const dashboardColors = {
    primary: '#4A90E2',
    orange: '#FF9F43',
    gray: '#7F8C8D',
};

function getWeeklyStatsData() {
    const dataNode = document.getElementById('dashboard-weekly-data');
    if (!dataNode) return [];
    try {
        return JSON.parse(dataNode.textContent) || [];
    } catch (error) {
        console.error('Impossible de lire les données hebdomadaires du dashboard.', error);
        return [];
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { initWeeklyChart(); }, 100);
});

window.addEventListener('themeChanged', () => {
    if (document.getElementById('weeklyChart')) initWeeklyChart();
});

function initWeeklyChart() {
    const ctx = document.getElementById('weeklyChart');
    if (!ctx) return;

    if (dashboardCharts.weekly) dashboardCharts.weekly.destroy();

    const isDarkMode = document.body.classList.contains('dark-mode');
    const textColor = isDarkMode ? '#BDC3C7' : '#7F8C8D';
    const weeklyStats = getWeeklyStatsData();

    dashboardCharts.weekly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: weeklyStats.map(d => d.day),
            datasets: [
                {
                    label: 'Présents',
                    data: weeklyStats.map(d => d.presents),
                    backgroundColor: dashboardColors.primary,
                    borderRadius: 6,
                },
                {
                    label: 'Absents',
                    data: weeklyStats.map(d => d.absents),
                    backgroundColor: dashboardColors.orange,
                    borderRadius: 6,
                },
                {
                    label: 'Incidents biométriques',
                    data: weeklyStats.map(d => d.unrecorded),
                    backgroundColor: dashboardColors.gray,
                    borderRadius: 6,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: textColor } }
            },
            scales: {
                y: { 
                    ticks: { color: textColor },
                    grid: { color: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }
                },
                x: { ticks: { color: textColor }, grid: { display: false } }
            }
        }
    });
}