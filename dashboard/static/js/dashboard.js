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

document.addEventListener('DOMContentLoaded', () => {
    loadRecentCheckIns();
    setTimeout(() => { initWeeklyChart(); }, 100);
});

window.addEventListener('themeChanged', () => {
    if (document.getElementById('weeklyChart')) initWeeklyChart();
});

function loadRecentCheckIns() {
    const tableBody = document.getElementById('recentTableBody');
    if (!tableBody) return;

    tableBody.innerHTML = testData.recentCheckIns
        .map(item => `
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

function initWeeklyChart() {
    const ctx = document.getElementById('weeklyChart');
    if (!ctx) return;

    if (dashboardCharts.weekly) dashboardCharts.weekly.destroy();

    const isDarkMode = document.body.classList.contains('dark-mode');
    const textColor = isDarkMode ? '#BDC3C7' : '#7F8C8D';

    dashboardCharts.weekly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: testData.weeklyStats.map(d => d.day),
            datasets: [
                {
                    label: 'Présents',
                    data: testData.weeklyStats.map(d => d.presents),
                    backgroundColor: dashboardColors.primary,
                    borderRadius: 6,
                },
                {
                    label: 'Absents',
                    data: testData.weeklyStats.map(d => d.absents),
                    backgroundColor: dashboardColors.orange,
                    borderRadius: 6,
                },
                {
                    label: 'Non reconnus',
                    data: testData.weeklyStats.map(d => d.unrecorded),
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