/**
 * APP.JS - Logique globale BioAttend
 * Gère : Sidebar, Mode Sombre, Menu Utilisateur
 */

document.addEventListener('DOMContentLoaded', () => {
    initializeGlobalListeners();
    initDarkMode();
});

function initializeGlobalListeners() {

    const hamburgerMenu = document.getElementById('hamburgerMenu');
    const sidebar = document.getElementById('sidebar');

    if (hamburgerMenu && sidebar) {
        hamburgerMenu.addEventListener('click', () => {
            hamburgerMenu.classList.toggle('active');
            sidebar.classList.toggle('active');
        });

        const navItems = sidebar.querySelectorAll('.nav-item');
        navItems.forEach((item) => {
            item.addEventListener('click', () => {
                hamburgerMenu.classList.remove('active');
                sidebar.classList.remove('active');
            });
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.sidebar') && !e.target.closest('.hamburger-menu')) {
                hamburgerMenu.classList.remove('active');
                sidebar.classList.remove('active');
            }
        });
    }

    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);

    const userMenuBtn = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (userMenuBtn && userDropdown) {
        userMenuBtn.addEventListener('click', () => {
            userDropdown.classList.toggle('active');
            userMenuBtn.classList.toggle('active');
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.user-menu-wrapper')) {
                userDropdown.classList.remove('active');
                userMenuBtn.classList.remove('active');
            }
        });
    }
}

function toggleTheme() {
    const isDarkMode = document.body.classList.toggle('dark-mode');
    const theme = isDarkMode ? 'dark' : 'light';

    localStorage.setItem('theme', theme);
    updateThemeIcon(theme);

    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: theme } }));
}

function updateThemeIcon(theme) {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        const icon = themeToggleBtn.querySelector('i');
        if (theme === 'dark') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
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