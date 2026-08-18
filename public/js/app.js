const SERVER = window.location.origin;
let currentView = 'chat';
let isListening = false;
let recognition = null;

// ===== BOOT SEQUENCE =====
document.addEventListener('DOMContentLoaded', () => {
    const bootBar = document.getElementById('bootBar');
    const bootStatus = document.getElementById('bootStatus');
    const bootScreen = document.getElementById('boot-screen');
    const mainApp = document.getElementById('main-app');

    const bootSteps = [
        { pct: 15, msg: 'Loading J.E.N.N.Y kernel...' },
        { pct: 30, msg: 'Initializing voice engine...' },
        { pct: 50, msg: 'Connecting to system telemetry...' },
        { pct: 70, msg: 'Loading widgets & weather data...' },
        { pct: 85, msg: 'Warming up neural pathways...' },
        { pct: 100, msg: 'All systems online. Welcome, Boss!' }
    ];

    let step = 0;
    const bootInterval = setInterval(() => {
        if (step < bootSteps.length) {
            bootBar.style.width = bootSteps[step].pct + '%';
            bootStatus.textContent = bootSteps[step].msg;
            step++;
        } else {
            clearInterval(bootInterval);
            setTimeout(() => {
                bootScreen.classList.add('fade-out');
                mainApp.classList.remove('hidden');
                setTimeout(() => bootScreen.remove(), 800);
                initApp();
            }, 600);
        }
    }, 500);
});

function initApp() {
    loadGreeting();
    loadWeather();
    loadClock();
    loadQuote();
    loadNews();
    loadFact();
    loadCrypto();
    loadNotes();
    loadTodos();
    loadVault();
    startSystemMonitor();
    setupNavigation();
    setupChat();
    setupVoice();
}

// ===== NAVIGATION =====
function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            switchView(view);
        });
    });

    document.getElementById('greetingClose').addEventListener('click', () => {
        document.getElementById('greetingBanner').style.display = 'none';
    });

    document.getElementById('overlayToggle').addEventListener('click', () => {
        document.body.classList.toggle('overlay-mode');
    });
}

function switchView(view) {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    document.querySelector(`[data-view="${view}"]`).classList.add('active');
    document.getElementById(`view-${view}`).classList.add('active');
    currentView = view;
}

// ===== CHAT =====
function setupChat() {
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');

    input.addEventListener('keypress', e => {
        if (e.key === 'Enter') sendMessage();
    });
    sendBtn.addEventListener('click', sendMessage);
}

function sendQuick(text) {
    document.getElementById('chatInput').value = text;
    sendMessage();
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    addMessage(text, 'user');
    showTyping();

    try {
        const resp = await fetch(`${SERVER}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ input: text })
        });
        const data = await resp.json();
        hideTyping();
        addMessage(data.reply || 'Something went wrong, Boss!', 'assistant');
    } catch (err) {
        hideTyping();
        addMessage('Server connection error. Is the server running, Boss?', 'assistant');
    }
}

function addMessage(text, type) {
    const container = document.getElementById('chatMessages');
    const msg = document.createElement('div');
    msg.className = `message ${type}`;
    msg.innerHTML = `
        <div class="msg-bubble">
            <div class="msg-label">${type === 'user' ? 'Harshit' : 'Jenny'}</div>
            ${escapeHtml(text)}
        </div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function showTyping() {
    const container = document.getElementById('chatMessages');
    const typing = document.createElement('div');
    typing.className = 'message assistant';
    typing.id = 'typingIndicator';
    typing.innerHTML = `
        <div class="msg-bubble">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
        </div>
    `;
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
}

function hideTyping() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

// ===== VOICE =====
function setupVoice() {
    const voiceBtn = document.getElementById('voiceBtn');
    voiceBtn.addEventListener('click', toggleVoice);

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            document.getElementById('chatInput').value = text;
            sendMessage();
            stopListening();
        };

        recognition.onerror = () => stopListening();
        recognition.onend = () => stopListening();
    }
}

function toggleVoice() {
    if (isListening) {
        stopListening();
    } else {
        startListening();
    }
}

function startListening() {
    if (!recognition) {
        addMessage('Voice recognition not supported in this browser, Boss!', 'assistant');
        return;
    }
    isListening = true;
    document.getElementById('voiceBtn').classList.add('listening');
    addMessage('Listening... Speak now, Boss!', 'system');
    recognition.start();
}

function stopListening() {
    isListening = false;
    document.getElementById('voiceBtn').classList.remove('listening');
    if (recognition) {
        try { recognition.stop(); } catch(e) {}
    }
}

// ===== GREETING =====
async function loadGreeting() {
    try {
        const resp = await fetch(`${SERVER}/api/greeting`);
        const data = await resp.json();
        document.getElementById('greetingText').textContent = data.greeting || 'Welcome, Boss!';
    } catch (e) {
        document.getElementById('greetingText').textContent =
            'Welcome to J.E.N.N.Y, Boss! All systems starting up...';
    }
}

// ===== WEATHER =====
async function loadWeather() {
    try {
        const resp = await fetch(`${SERVER}/api/weather`);
        const data = await resp.json();
        document.getElementById('widgetTemp').textContent = `${data.temp}°C`;
        document.getElementById('widgetDesc').textContent = data.desc || 'Unknown';
        document.getElementById('widgetLocation').textContent = data.city || 'Unknown';
    } catch (e) {
        document.getElementById('widgetTemp').textContent = '--°C';
        document.getElementById('widgetDesc').textContent = 'Offline';
    }
}

// ===== CLOCK =====
function loadClock() {
    function update() {
        const now = new Date();
        const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
        const date = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        document.getElementById('widgetTime').textContent = time;
        document.getElementById('widgetDate').textContent = date;
    }
    update();
    setInterval(update, 1000);
}

// ===== QUOTE =====
async function loadQuote() {
    try {
        const resp = await fetch(`${SERVER}/api/quote`);
        const data = await resp.json();
        document.getElementById('widgetQuote').textContent = `"${data.text || 'Stay motivated, Boss!'}"`;
        document.getElementById('widgetQuoteAuthor').textContent = `— ${data.author || 'Unknown'}`;
    } catch (e) {
        document.getElementById('widgetQuote').textContent = '"The only way to do great work is to love what you do."';
        document.getElementById('widgetQuoteAuthor').textContent = '— Steve Jobs';
    }
}

// ===== NEWS =====
async function loadNews() {
    try {
        const resp = await fetch(`${SERVER}/api/news`);
        const data = await resp.json();
        const body = document.getElementById('newsBody');
        body.innerHTML = '';
        (data.stories || []).slice(0, 5).forEach(story => {
            const item = document.createElement('div');
            item.className = 'news-item';
            item.textContent = story.title;
            if (story.url) {
                item.onclick = () => window.open(story.url, '_blank');
            }
            body.appendChild(item);
        });
        if (!data.stories || data.stories.length === 0) {
            body.innerHTML = '<div class="news-item">No news available (offline)</div>';
        }
    } catch (e) {
        document.getElementById('newsBody').innerHTML = '<div class="news-item">Could not load news</div>';
    }
}

// ===== FACT =====
async function loadFact() {
    try {
        const resp = await fetch(`${SERVER}/api/fact`);
        const data = await resp.json();
        document.getElementById('widgetFact').textContent = data.fact || 'No fact available right now.';
    } catch (e) {
        document.getElementById('widgetFact').textContent = 'Could not load fact.';
    }
}

// ===== CRYPTO =====
async function loadCrypto() {
    try {
        const resp = await fetch(`${SERVER}/api/crypto`);
        const data = await resp.json();
        const body = document.getElementById('cryptoBody');
        body.innerHTML = '';
        for (const [coin, info] of Object.entries(data)) {
            const price = info.usd || 0;
            const change = info.usd_24h_change || 0;
            const changeClass = change >= 0 ? 'up' : 'down';
            const changeSign = change >= 0 ? '+' : '';
            body.innerHTML += `
                <div class="crypto-item">
                    <span class="crypto-name">${coin.toUpperCase()}</span>
                    <span class="crypto-price">$${price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    <span class="crypto-change ${changeClass}">${changeSign}${change.toFixed(2)}%</span>
                </div>
            `;
        }
        if (Object.keys(data).length === 0) {
            body.innerHTML = '<div class="crypto-item"><span class="crypto-name">Offline</span></div>';
        }
    } catch (e) {
        document.getElementById('cryptoBody').innerHTML = '<div class="crypto-item"><span class="crypto-name">Could not load</span></div>';
    }
}

// ===== SYSTEM MONITOR =====
function startSystemMonitor() {
    async function update() {
        try {
            const resp = await fetch(`${SERVER}/api/system-status`);
            const data = await resp.json();

            document.getElementById('cpuValue').textContent = `${data.cpu || 0}%`;
            document.getElementById('cpuBar').style.width = `${data.cpu || 0}%`;

            document.getElementById('ramValue').textContent = `${data.ram || 0}%`;
            document.getElementById('ramBar').style.width = `${data.ram || 0}%`;
            document.getElementById('ramDetail').textContent = `${data.ram_used || '--'} / ${data.ram_total || '--'} GB`;

            document.getElementById('diskValue').textContent = `${data.disk?.percent || 0}%`;
            document.getElementById('diskBar').style.width = `${data.disk?.percent || 0}%`;
            document.getElementById('diskDetail').textContent = `${data.disk?.free || '--'} free`;

            const bat = data.battery || {};
            document.getElementById('batteryValue').textContent = `${bat.percent || 0}%`;
            document.getElementById('batteryDetail').textContent = bat.charging ? 'Charging' : 'On Battery';

            const net = data.network || {};
            if (net.bytes_recv) {
                document.getElementById('netValue').textContent = `${(net.bytes_recv / (1024*1024)).toFixed(0)} MB`;
                document.getElementById('netDetail').textContent = 'Received';
            }

            document.getElementById('osValue').textContent = data.os || 'Windows';
            document.getElementById('hostnameValue').textContent = data.hostname || '--';
            document.getElementById('uptimeDisplay').textContent = `Uptime: ${data.uptime || '--'}`;
        } catch (e) {
            // Silently fail
        }
    }
    update();
    setInterval(update, 5000);
}

// ===== NOTES =====
async function loadNotes() {
    try {
        const resp = await fetch(`${SERVER}/api/notes`);
        const data = await resp.json();
        const list = document.getElementById('notesList');
        list.innerHTML = '';
        (data.notes || []).reverse().forEach(note => {
            const item = document.createElement('div');
            item.className = 'note-item';
            item.textContent = note.text;
            list.appendChild(item);
        });
    } catch (e) {}
}

async function saveNote() {
    const input = document.getElementById('notesInput');
    const text = input.value.trim();
    if (!text) return;
    try {
        await fetch(`${SERVER}/api/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        input.value = '';
        loadNotes();
    } catch (e) {}
}

// ===== TODOS =====
async function loadTodos() {
    try {
        const resp = await fetch(`${SERVER}/api/todos`);
        const data = await resp.json();
        const list = document.getElementById('todosList');
        list.innerHTML = '';
        (data.todos || []).forEach((todo, idx) => {
            const item = document.createElement('div');
            item.className = 'todo-item';
            item.innerHTML = `
                <div class="todo-check ${todo.done ? 'done' : ''}" onclick="completeTodo(${idx})"></div>
                <span class="todo-text ${todo.done ? 'done' : ''}">${escapeHtml(todo.text)}</span>
            `;
            list.appendChild(item);
        });
    } catch (e) {}
}

async function addTodo() {
    const input = document.getElementById('todoInput');
    const text = input.value.trim();
    if (!text) return;
    try {
        await fetch(`${SERVER}/api/todos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add', text })
        });
        input.value = '';
        loadTodos();
    } catch (e) {}
}

async function completeTodo(idx) {
    try {
        await fetch(`${SERVER}/api/todos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'complete', index: idx })
        });
        loadTodos();
    } catch (e) {}
}

// ===== VAULT =====
async function loadVault() {
    try {
        const resp = await fetch(`${SERVER}/api/vault`);
        const data = await resp.json();
        const list = document.getElementById('vaultList');
        list.innerHTML = '';
        (data.entries || []).reverse().forEach(entry => {
            const item = document.createElement('div');
            item.className = 'vault-item';
            item.textContent = entry.text;
            list.appendChild(item);
        });
    } catch (e) {}
}

async function addVault() {
    const input = document.getElementById('vaultInput');
    const text = input.value.trim();
    if (!text) return;
    try {
        await fetch(`${SERVER}/api/vault`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        input.value = '';
        loadVault();
    } catch (e) {}
}

async function clearVault() {
    try {
        await fetch(`${SERVER}/api/vault`, { method: 'DELETE' });
        loadVault();
    } catch (e) {}
}

// ===== UTILS =====
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
