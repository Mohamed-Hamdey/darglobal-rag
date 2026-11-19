const API_BASE = '';
let isStreaming = false;

document.addEventListener('DOMContentLoaded', () => {
    fetchMeta();
    setupEventListeners();
});

async function fetchMeta() {
    try {
        const res = await fetch(`${API_BASE}/api/meta`);
        const data = await res.json();
        document.getElementById('modelBadge').textContent = `Model: ${data.models[0].split(':')[0]} | Data: ${data.data_date}`;
    } catch (e) {
        document.getElementById('modelBadge').textContent = 'Offline';
    }
}

function setupEventListeners() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    document.querySelectorAll('.starter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.dataset.q;
            sendMessage();
        });
    });
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    if (!message || isStreaming) return;

    // Hide empty state
    document.getElementById('emptyState').style.display = 'none';
    
    // Add user message
    addMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';
    
    // Add assistant placeholder with typing indicator
    const assistantDiv = addMessage('', 'assistant');
    const textDiv = assistantDiv.querySelector('.message-text');
    textDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    
    isStreaming = true;
    const stallTimer = setTimeout(() => {
    if (isStreaming) {
        textDiv.textContent = fullText || "⚠️ The model is busy or rate-limited. Please try again in a moment.";
        isStreaming = false;
        document.getElementById('sendBtn').disabled = false;
    }
}, 25000);
    document.getElementById('sendBtn').disabled = true;

    const source = document.getElementById('sourceFilter').value;
    let fullText = '';
    let citationsHtml = '';

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, source })
        });
        if (!response.headers.get('content-type')?.includes('text/event-stream')) {
            const j = await response.json().catch(() => ({}));
            textDiv.textContent = j.answer || "⚠️ Unexpected response.";
            isStreaming = false; document.getElementById('sendBtn').disabled = false;
            clearTimeout(stallTimer);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n').filter(line => line.startsWith('data: '));

            for (const line of lines) {
                try {
                    const data = JSON.parse(line.slice(6));
                    if (data.type === 'token') {
                        fullText += data.content;
                        textDiv.textContent = fullText; // Safe text rendering
                    } else if (data.type === 'citations') {
                        citationsHtml = renderCitations(data.data);
                    } else if (data.type === 'done') {
                        isStreaming = false;
                        document.getElementById('sendBtn').disabled = false;
                    }
                } catch (e) { /* ignore parse errors on stream boundaries */ }
            }
        }

        if (citationsHtml) {
            textDiv.innerHTML = fullText.replace(/\n/g, '<br>') + `<div class="citations">${citationsHtml}</div>`;
        }

    } catch (error) {
        textDiv.textContent = '⚠️ Error connecting to the assistant. Please try again.';
        isStreaming = false;
        document.getElementById('sendBtn').disabled = false;
    }
}

function addMessage(text, role) {
    const container = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `<div class="message-text">${text}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function renderCitations(citations) {
    return citations.map(c => {
        const companyClass = c.company.toLowerCase() === 'darglobal' ? 'dg' : 'wa';
        return `<a href="${c.url}" target="_blank" class="citation-chip ${companyClass}">
            [${c.id}] ${c.title} · ${c.company} ↗
        </a>`;
    }).join('');
}

// Auto-resize textarea
document.getElementById('messageInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});