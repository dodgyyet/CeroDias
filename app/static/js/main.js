// CeroDias CTF Platform — Main JavaScript

document.addEventListener('DOMContentLoaded', function () {
    const fab      = document.getElementById('chat-fab');
    const panel    = document.getElementById('chatbot-panel');
    const closeBtn = document.getElementById('chatbot-close');
    const input    = document.getElementById('chatbot-input');
    const sendBtn  = document.getElementById('chatbot-send');
    const messages = document.getElementById('chatbot-messages');

    // Chatbot only exists when logged in
    if (!fab || !panel) return;

    // ── FAB toggle ─────────────────────────────────────────────────
    fab.addEventListener('click', function () {
        const isOpen = panel.classList.contains('open');
        if (isOpen) {
            closePanel();
        } else {
            openPanel();
        }
    });

    if (closeBtn) closeBtn.addEventListener('click', closePanel);

    // Close panel when clicking outside
    document.addEventListener('click', function (e) {
        if (panel.classList.contains('open') && !panel.contains(e.target) && !fab.contains(e.target)) {
            closePanel();
        }
    });

    function openPanel() {
        panel.classList.add('open');
        fab.classList.add('open');
        fab.setAttribute('title', 'Close assistant');
        document.getElementById('chat-fab-icon').textContent = '\u2715';
        if (input) input.focus();
    }

    function closePanel() {
        panel.classList.remove('open');
        fab.classList.remove('open');
        fab.setAttribute('title', 'Chat with CERA');
        document.getElementById('chat-fab-icon').textContent = '\uD83D\uDCAC';
    }

    // ── Load history ───────────────────────────────────────────────
    loadChatHistory();

    // ── Send on button click or Enter ──────────────────────────────
    if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);

    if (input) {
        input.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') sendChatMessage();
        });
    }
});

// ── Send message ────────────────────────────────────────────────────
async function sendChatMessage() {
    const input   = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send');
    const message = input.value.trim();
    if (!message) return;

    addMessageToUI(message, 'user');
    input.value = '';
    input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;

    const typingId = showTypingIndicator();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `message=${encodeURIComponent(message)}`
        });
        const data = await response.json();
        removeTypingIndicator(typingId);

        if (data.success) {
            addMessageToUI(data.message, 'bot');
        } else {
            addMessageToUI('Error: ' + data.message, 'bot');
        }
    } catch (err) {
        removeTypingIndicator(typingId);
        addMessageToUI('Connection error. Please try again.', 'bot');
    } finally {
        input.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        input.focus();
    }
}

// ── Add message bubble ───────────────────────────────────────────────
function addMessageToUI(text, sender) {
    const messages = document.getElementById('chatbot-messages');
    if (!messages) return;

    const div = document.createElement('div');
    div.className = 'chatbot-message' + (sender === 'user' ? ' chatbot-user' : '');

    if (sender === 'user') {
        div.innerHTML = `<div class="chatbot-user-text">${escapeHtml(text)}</div>`;
    } else {
        // Bot responses rendered as raw HTML (intentional XSS surface).
        // Chain: prompt injection → AI returns HTML payload → innerHTML renders it.
        // User messages remain escaped above.
        div.innerHTML = `<div class="chatbot-bot-text">${text}</div>`;
    }

    messages.appendChild(div);
    scrollToBottom(messages);
}

// ── Typing indicator ─────────────────────────────────────────────────
function showTypingIndicator() {
    const messages = document.getElementById('chatbot-messages');
    if (!messages) return null;

    const id = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'chatbot-message';
    div.innerHTML = `
        <div class="chatbot-bot-text typing-indicator">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>`;
    messages.appendChild(div);
    scrollToBottom(messages);
    return id;
}

function removeTypingIndicator(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ── Load chat history ─────────────────────────────────────────────────
async function loadChatHistory() {
    try {
        const response = await fetch('/chat/history');
        const data = await response.json();
        const messages = document.getElementById('chatbot-messages');
        if (data.success && data.messages.length > 0) {
            messages.innerHTML = '';
            for (const msg of data.messages) {
                addMessageToUI(msg.user_message, 'user');
                addMessageToUI(msg.bot_response, 'bot');
            }
        } else {
            addMessageToUI("Hi, I'm CERA — CeroDias's support agent. Ask me about our certifications, pricing, or anything I can help with.", 'bot');
        }
    } catch (err) {
        console.error('Error loading chat history:', err);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────
function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
