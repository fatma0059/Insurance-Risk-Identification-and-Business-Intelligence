// ============ CONFIGURATION ============
const CONFIG = {
    USERS: {
        'admin@astree.ma': { password: 'astreeadmin', role: 'admin', name: 'Administrateur ASTREE' },
        'agent@astree.ma': { password: 'astreeagent', role: 'agent', name: 'Agent ASTREE' },
        'fatma@gmail.com': { password: 'astreeadmin', role: 'admin', name: 'Fatma Admin' }
    },
    PREDICTION_API: 'http://localhost:5000',
    CHAT_API: 'http://localhost:5001',
    BACKEND_API: '/astree/web/',
    // URLs des dashboards Power BI distincts
    POWERBI: {
        admin: 'https://app.powerbi.com/view?r=eyJrIjoiNjI5M2RkNTMtMWYyYS00ODM4LTg0OGMtZDE5ZWFiZTliMmU2IiwidCI6ImRiZDY2NjRkLTRlYjktNDZlYi05OWQ4LTVjNDNiYTE1M2M2MSIsImMiOjl9',
        agent: 'https://app.powerbi.com/view?r=eyJrIjoiMDM1ZGZhZjctYjFjMC00ZWY3LTllYzMtOGJkNTg0MDU2ZDQyIiwidCI6ImRiZDY2NjRkLTRlYjktNDZlYi05OWQ4LTVjNDNiYTE1M2M2MSIsImMiOjl9'
    }
};

// ============ AUTHENTIFICATION ============
function togglePassword() {
    const passwordInput = document.getElementById('password');
    const eyeIcon = document.getElementById('eye-icon');
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        eyeIcon.className = 'fas fa-eye';
    }
}

function login() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();
    const errorMsg = document.getElementById('error-message');

    errorMsg.textContent = '';

    if (!email || !password) {
        errorMsg.textContent = 'Veuillez saisir votre email et mot de passe.';
        return;
    }

    const user = CONFIG.USERS[email];

    if (user && user.password === password) {
        const userData = {
            email: email,
            name: user.name,
            role: user.role,
            loginTime: new Date().toISOString()
        };
        localStorage.setItem('astree_user', JSON.stringify(userData));
        window.location.href = 'dashboard.html';
    } else {
        errorMsg.textContent = '❌ Email ou mot de passe incorrect.';
        document.getElementById('password').value = '';
        document.getElementById('password').focus();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('password');
    const emailInput = document.getElementById('email');
    if (passwordInput) passwordInput.addEventListener('keypress', e => { if (e.key === 'Enter') login(); });
    if (emailInput) emailInput.addEventListener('keypress', e => { if (e.key === 'Enter') login(); });
});

// ============ DASHBOARD ============
let currentUser = null;
let currentPage = 'dashboard';

function initDashboard() {
    const userStr = localStorage.getItem('astree_user');
    if (!userStr) {
        window.location.href = 'index.html';
        return;
    }

    currentUser = JSON.parse(userStr);

    document.getElementById('userName').textContent = currentUser.name;
    document.getElementById('userRole').textContent = currentUser.role === 'admin' ? 'Administrateur' : 'Agent';

    const badge = document.getElementById('roleBadge');
    badge.textContent = currentUser.role === 'admin' ? 'Admin' : 'Agent';
    if (currentUser.role === 'admin') badge.classList.add('admin');

    updateDate();
    setInterval(updateDate, 60000);
    loadPage('dashboard');
}

function updateDate() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateEl = document.getElementById('currentDate');
    if (dateEl) dateEl.textContent = now.toLocaleDateString('fr-FR', options);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sidebarOverlay').classList.toggle('active');
}

function logout() {
    if (confirm('Êtes-vous sûr de vouloir vous déconnecter ?')) {
        localStorage.removeItem('astree_user');
        window.location.href = 'index.html';
    }
}

function refreshPage() {
    const iframe = document.getElementById('powerbiFrame');
    if (iframe) {
        iframe.src = iframe.src;
    }
    loadPage(currentPage);
}

function loadPage(page) {
    currentPage = page;
    const content = document.getElementById('contentArea');
    const title = document.getElementById('pageTitle');

    const titles = {
        'dashboard': 'Dashboard',
        'ia': 'Assistance IA',
        'chat': 'Chat'
    };
    if (title) title.textContent = titles[page] || page;

    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const activeNav = document.querySelector(`[data-page="${page}"]`);
    if (activeNav) activeNav.classList.add('active');

    switch(page) {
        case 'dashboard': loadDashboard(content); break;
        case 'ia': loadIA(content); break;
        case 'chat': loadChat(content); break;
        default: content.innerHTML = '<div class="empty-state"><i class="fas fa-construction"></i><p>Page en construction...</p></div>';
    }

    if (window.innerWidth <= 768) {
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('sidebarOverlay').classList.remove('active');
    }
}

// ============ DASHBOARD POWER BI (IFRAME) ============
function loadDashboard(container) {
    const isAdmin = currentUser && currentUser.role === 'admin';
    const dashboardUrl = isAdmin ? CONFIG.POWERBI.admin : CONFIG.POWERBI.agent;
    const dashboardLabel = isAdmin ? 'Administrateur' : 'Agent';
    const dashboardTitle = isAdmin ? 'admins astree' : 'agents astree';

    container.innerHTML = `
        <div class="dashboard-powerbi">
            <div class="dashboard-header">
                <h3><i class="fas fa-chart-pie"></i> Dashboard ${dashboardLabel}</h3>
                <p style="color:var(--gray-500);margin-top:4px;font-size:14px;">
                    <i class="fas fa-info-circle"></i>
                    ${isAdmin ? 'Vue complète - Toutes les données' : 'Vue agent - Données restreintes'}
                </p>
                <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;">
                    <button class="btn-search" onclick="refreshDashboard()">
                        <i class="fas fa-sync-alt"></i> Rafraîchir
                    </button>
                    <button class="btn-search btn-search-secondary" onclick="openFullscreen()">
                        <i class="fas fa-expand"></i> Plein écran
                    </button>
                </div>
            </div>

            <div class="dashboard-viewer">
                <iframe
                    id="powerbiFrame"
                    title="${dashboardTitle}"
                    src="${dashboardUrl}"
                    frameborder="0"
                    allowFullScreen="true"
                    style="width:100%;height:600px;border:none;border-radius:8px;"
                    loading="lazy"
                ></iframe>
            </div>

            <div class="dashboard-info">
                <div class="info-grid">
                    <div class="info-card">
                        <i class="fas fa-user-tie"></i>
                        <div>
                            <h5>Rôle</h5>
                            <p>${isAdmin ? 'Administrateur' : 'Agent'}</p>
                        </div>
                    </div>
                    <div class="info-card">
                        <i class="fas fa-chart-line"></i>
                        <div>
                            <h5>Dashboard</h5>
                            <p>${dashboardTitle}</p>
                        </div>
                    </div>
                    <div class="info-card">
                        <i class="fas fa-clock"></i>
                        <div>
                            <h5>Dernière mise à jour</h5>
                            <p>${new Date().toLocaleString('fr-FR')}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function refreshDashboard() {
    const iframe = document.getElementById('powerbiFrame');
    if (iframe) {
        iframe.src = iframe.src;
        showNotification('✅ Dashboard rafraîchi avec succès');
    }
}

function openFullscreen() {
    const iframe = document.getElementById('powerbiFrame');
    if (iframe) {
        if (iframe.requestFullscreen) {
            iframe.requestFullscreen();
        } else if (iframe.webkitRequestFullscreen) {
            iframe.webkitRequestFullscreen();
        } else if (iframe.msRequestFullscreen) {
            iframe.msRequestFullscreen();
        }
    }
}

function showNotification(message) {
    document.querySelectorAll('.notification-toast').forEach(el => el.remove());

    const toast = document.createElement('div');
    toast.className = 'notification-toast';
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: var(--gray-800);
        color: white;
        padding: 14px 24px;
        border-radius: 8px;
        font-size: 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 9999;
        animation: slideUp 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

