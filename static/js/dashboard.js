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

function getWorkHoursData() {
    const dataNode = document.getElementById('employee-work-hours-data');
    if (!dataNode) return { labels: [], data: [] };
    try {
        const parsed = JSON.parse(dataNode.textContent);
        return parsed && typeof parsed === 'object' ? parsed : { labels: [], data: [] };
    } catch (error) {
        console.error('Impossible de lire les données des prestations.', error);
        return { labels: [], data: [] };
    }
}

function setupChartExports() {
    document.querySelectorAll('.chart-export-btn').forEach(button => {
        button.addEventListener('click', () => {
            const chartId = button.getAttribute('data-chart-id');
            const fileName = button.getAttribute('data-file-name') || 'graphique';
            const canvas = document.getElementById(chartId);
            if (!canvas) return;

            const link = document.createElement('a');
            link.href = canvas.toDataURL('image/png');
            link.download = `${fileName}.png`;
            link.click();
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        initWeeklyChart();
        initWorkHoursChart();
        setupChartExports();
    }, 100);
});

window.addEventListener('themeChanged', () => {
    if (document.getElementById('weeklyChart')) initWeeklyChart();
    if (document.getElementById('workHoursChart')) initWorkHoursChart();
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
                    label: 'Incidents sécurité',
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

function initWorkHoursChart() {
    const canvas = document.getElementById('workHoursChart');
    if (!canvas) return;

    const isDarkMode = document.body.classList.contains('dark-mode');
    const textColor = isDarkMode ? '#BDC3C7' : '#7F8C8D';
    const workHours = getWorkHoursData();

    if (typeof Chart !== 'undefined') {
        if (dashboardCharts.workHours) dashboardCharts.workHours.destroy();

        dashboardCharts.workHours = new Chart(canvas, {
            type: 'line',
            data: {
                labels: workHours.labels,
                datasets: [{
                    label: 'Heures prestées',
                    data: workHours.data,
                    borderColor: dashboardColors.primary,
                    backgroundColor: 'rgba(74, 144, 226, 0.18)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: textColor } }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Heures', color: textColor },
                        ticks: { color: textColor },
                        grid: { color: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }
                    },
                    x: {
                        ticks: { color: textColor },
                        grid: { display: false }
                    }
                }
            }
        });
        return;
    }

    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.offsetWidth || 600;
    const height = canvas.height = canvas.offsetHeight || 280;
    const padding = 40;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = isDarkMode ? '#111827' : '#ffffff';
    ctx.fillRect(0, 0, width, height);

    const values = workHours.data || [];
    const labels = workHours.labels || [];
    const maxValue = Math.max(...values, 1);

    ctx.strokeStyle = isDarkMode ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.08)';
    ctx.beginPath();
    ctx.moveTo(padding, padding / 2);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding / 2, height - padding);
    ctx.stroke();

    if (!values.length) {
        ctx.fillStyle = textColor;
        ctx.font = '14px sans-serif';
        ctx.fillText('Aucune donnée à afficher', padding, height / 2);
        return;
    }

    const barWidth = Math.max((width - padding * 2) / values.length - 12, 18);
    values.forEach((value, index) => {
        const x = padding + index * ((width - padding * 2) / values.length) + 6;
        const barHeight = ((height - padding * 1.5) * value) / maxValue;
        const y = height - padding - barHeight;

        ctx.fillStyle = 'rgba(74, 144, 226, 0.75)';
        ctx.fillRect(x, y, barWidth, barHeight);

        ctx.fillStyle = textColor;
        ctx.font = '11px sans-serif';
        ctx.fillText(String(value), x, y - 6);
        ctx.fillText(labels[index] || '', x, height - padding + 16);
    });
}