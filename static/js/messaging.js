let selectedUserId = null;
let selectedContact = null;
let messagePollTimer = null;
let conversationsPollTimer = null;
let sendInFlight = false;
let messagesRequestId = 0;
let messagesAbort = null;
let knownMessageIds = new Set();

function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i += 1) {
        const cookie = cookies[i].trim();
        if (cookie.startsWith(name + '=')) {
            return decodeURIComponent(cookie.substring(name.length + 1));
        }
    }
    return '';
}

function getCsrfToken() {
    const fromCookie = getCookie('csrftoken');
    if (fromCookie) {
        window.MESSAGING_CSRF = fromCookie;
        return fromCookie;
    }
    const input = document.querySelector('#messageForm input[name="csrfmiddlewaretoken"]');
    if (input?.value) {
        window.MESSAGING_CSRF = input.value;
        return input.value;
    }
    return window.MESSAGING_CSRF || '';
}

async function refreshCsrfToken() {
    if (!window.MESSAGING_URLS?.csrf) {
        return getCsrfToken();
    }
    try {
        const res = await fetch(window.MESSAGING_URLS.csrf, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!res.ok) return getCsrfToken();
        const data = await res.json();
        if (data.csrfToken) {
            window.MESSAGING_CSRF = data.csrfToken;
            const input = document.querySelector('#messageForm input[name="csrfmiddlewaretoken"]');
            if (input) input.value = data.csrfToken;
            return data.csrfToken;
        }
    } catch (e) {
        // ignore
    }
    return getCsrfToken();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function urlForUser(template, userId) {
    return template.replace(/\/0(\/|$)/, `/${userId}$1`);
}

function showToast(message) {
    const toast = document.getElementById('msgToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('visible');
    setTimeout(() => toast.classList.remove('visible'), 2800);
}

function stopPolling() {
    if (messagePollTimer) {
        clearInterval(messagePollTimer);
        messagePollTimer = null;
    }
    if (conversationsPollTimer) {
        clearInterval(conversationsPollTimer);
        conversationsPollTimer = null;
    }
    if (messagesAbort) {
        messagesAbort.abort();
        messagesAbort = null;
    }
}

function renderAvatar(data, className = 'user-avatar') {
    if (data.avatar_url) {
        return `<div class="${className}"><img src="${escapeHtml(data.avatar_url)}" alt=""></div>`;
    }
    const initial = data.initial || (data.name || data.username || '?').charAt(0).toUpperCase();
    return `<div class="${className}">${escapeHtml(initial)}</div>`;
}

function renderMessage(msg) {
    const messageClass = msg.is_sent ? 'sent' : 'received';
    const callClass = msg.message_type === 'call' ? ' call' : '';
    const idAttr = msg.id != null ? ` data-message-id="${msg.id}"` : '';
    return `
        <div class="message ${messageClass}${callClass}"${idAttr}>
            <div class="message-body">
                <div class="message-bubble">${escapeHtml(msg.content)}</div>
                <div class="message-time">${escapeHtml(msg.time_short || msg.created_at || '')}</div>
            </div>
        </div>
    `;
}

function scrollMessagesToBottom() {
    const container = document.getElementById('messagesContainer');
    if (!container) return;
    container.scrollTop = container.scrollHeight;
}

function appendMessage(msg) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    if (msg.id != null) {
        if (knownMessageIds.has(msg.id)) return;
        knownMessageIds.add(msg.id);
        if (container.querySelector(`[data-message-id="${msg.id}"]`)) return;
    }

    const empty = container.querySelector('.empty-state');
    if (empty) empty.remove();

    container.insertAdjacentHTML('beforeend', renderMessage(msg));
    scrollMessagesToBottom();
}

function renderMessages(messages) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    knownMessageIds = new Set(
        (messages || []).filter((msg) => msg.id != null).map((msg) => msg.id),
    );

    if (!messages.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💬</div>
                Aucun message. Écrivez le premier message ou lancez un appel.
            </div>`;
        return;
    }
    container.innerHTML = messages.map(renderMessage).join('');
    scrollMessagesToBottom();
}

function updateChatHeader(contact) {
    const avatar = document.getElementById('chatHeaderAvatar');
    const title = document.getElementById('chatTitle');
    const subtitle = document.getElementById('chatSubtitle');
    const callBtn = document.getElementById('callBtn');

    if (!contact) {
        avatar.classList.remove('visible');
        avatar.innerHTML = '?';
        title.textContent = 'Sélectionnez une conversation';
        subtitle.textContent = 'Choisissez un collègue dans la liste';
        callBtn.disabled = true;
        return;
    }

    if (contact.avatar_url) {
        avatar.innerHTML = `<img src="${escapeHtml(contact.avatar_url)}" alt="">`;
    } else {
        avatar.textContent = (contact.name || contact.username || '?').charAt(0).toUpperCase();
    }
    avatar.classList.add('visible');
    title.textContent = contact.name || contact.username;
    subtitle.textContent = `${contact.branch || ''} · ${contact.role || ''}${contact.phone ? ' · ' + contact.phone : ''}`;
    callBtn.disabled = false;
}

function loadConversations() {
    fetch(window.MESSAGING_URLS.conversations, { credentials: 'same-origin' })
        .then((response) => {
            if (response.redirected && response.url.includes('/login')) {
                stopPolling();
                throw new Error('auth');
            }
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then((data) => renderConversations(data.conversations || []))
        .catch((error) => {
            if (error.message === 'auth') return;
            console.error('Conversations error:', error);
            const list = document.getElementById('usersList');
            if (list && !list.querySelector('.user-item')) {
                list.innerHTML = '<div class="empty-state">Impossible de charger les contacts. Rechargez la page.</div>';
            }
        });
}

function renderConversations(conversations) {
    const list = document.getElementById('usersList');
    if (!list) return;

    if (!conversations.length) {
        list.innerHTML = '<div class="empty-state">Aucun collègue disponible</div>';
        return;
    }

    list.innerHTML = conversations.map((conversation) => `
        <div class="user-item" data-user-id="${conversation.id}" onclick="openUserChat(${conversation.id}, event)">
            ${renderAvatar(conversation)}
            <div class="user-info">
                <h3>${escapeHtml(conversation.name)}</h3>
                <p class="user-meta">${escapeHtml(conversation.branch)}</p>
                <p class="user-preview">${escapeHtml(conversation.last_message)}</p>
            </div>
            <div class="unread-badge ${conversation.unread_count > 0 ? 'visible' : ''}">
                ${conversation.unread_count > 0 ? conversation.unread_count : ''}
            </div>
        </div>
    `).join('');

    if (selectedUserId) {
        const active = list.querySelector(`[data-user-id="${selectedUserId}"]`);
        if (active) active.classList.add('active');
    }
}

function openUserChat(userId, event) {
    selectedUserId = Number(userId);
    knownMessageIds = new Set();
    document.querySelectorAll('.user-item').forEach((item) => item.classList.remove('active'));
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    }

    document.getElementById('messageForm').classList.remove('hidden');
    loadMessages(selectedUserId, true);
    startMessagePolling();
}

function loadMessages(userId, focusInput = false) {
    const targetId = Number(userId);
    if (!targetId) return;

    const requestId = ++messagesRequestId;
    if (messagesAbort) messagesAbort.abort();
    messagesAbort = new AbortController();

    fetch(urlForUser(window.MESSAGING_URLS.messages, targetId), {
        credentials: 'same-origin',
        signal: messagesAbort.signal,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        cache: 'no-store',
    })
        .then((response) => {
            if (response.redirected && response.url.includes('/login')) {
                stopPolling();
                throw new Error('auth');
            }
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then((data) => {
            // Ignore les réponses obsolètes (évite d'écraser un message tout juste envoyé)
            if (requestId !== messagesRequestId || Number(selectedUserId) !== targetId) {
                return;
            }
            selectedContact = data.contact;
            updateChatHeader(data.contact);
            renderMessages(data.messages || []);
            if (focusInput) {
                const input = document.getElementById('messageInput');
                input?.focus();
                autoResizeMessageInput(input);
            }
        })
        .catch((error) => {
            if (error.name === 'AbortError' || error.message === 'auth') return;
            if (requestId !== messagesRequestId) return;
            document.getElementById('messagesContainer').innerHTML =
                '<div class="empty-state">Erreur de chargement des messages</div>';
        });
}

function startMessagePolling() {
    if (messagePollTimer) clearInterval(messagePollTimer);
    messagePollTimer = setInterval(() => {
        if (selectedUserId) loadMessages(selectedUserId, false);
    }, 4000);
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage(event);
    }
}

function autoResizeMessageInput(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
}

async function postWithCsrf(url, formData, retried = false) {
    const csrfToken = retried ? await refreshCsrfToken() : getCsrfToken();
    formData.set('csrfmiddlewaretoken', csrfToken);

    const response = await fetch(url, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken,
        },
    });

    if (response.status === 403 && !retried) {
        return postWithCsrf(url, formData, true);
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const err = new Error(data.error || `HTTP ${response.status}`);
        err.status = response.status;
        throw err;
    }
    return data;
}

function updateConversationPreview(userId, preview) {
    const item = document.querySelector(`.user-item[data-user-id="${userId}"]`);
    if (!item) return;
    const previewEl = item.querySelector('.user-preview');
    if (previewEl) previewEl.textContent = preview;
    const list = document.getElementById('usersList');
    if (list && item !== list.firstElementChild) {
        list.prepend(item);
    }
}

async function sendMessage(event) {
    if (event) event.preventDefault();
    if (!selectedUserId) {
        showToast('Sélectionnez un contact d\'abord');
        return;
    }
    if (sendInFlight) return;

    const messageInput = document.getElementById('messageInput');
    const content = messageInput.value.trim();
    if (!content) return;

    sendInFlight = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';

    appendMessage({
        content,
        is_sent: true,
        message_type: 'text',
        time_short: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    });
    updateConversationPreview(selectedUserId, content);

    const formData = new FormData();
    formData.append('content', content);

    try {
        const data = await postWithCsrf(
            urlForUser(window.MESSAGING_URLS.send, selectedUserId),
            formData,
        );
        if (data.ok && data.message) {
            appendMessage(data.message);
            updateConversationPreview(selectedUserId, data.message.content);
            loadMessages(selectedUserId, false);
            loadConversations();
        } else if (data.error) {
            showToast(data.error);
            loadMessages(selectedUserId, false);
        }
    } catch (e) {
        showToast('Erreur lors de l\'envoi');
        loadMessages(selectedUserId, false);
    } finally {
        sendInFlight = false;
        messageInput.focus();
    }
}

async function initiateCall() {
    if (!selectedUserId) {
        showToast('Sélectionnez un contact pour appeler');
        return;
    }

    const formData = new FormData();
    try {
        const data = await postWithCsrf(
            urlForUser(window.MESSAGING_URLS.call, selectedUserId),
            formData,
        );
        loadMessages(selectedUserId, false);
        loadConversations();
        openCallModal(data);
    } catch (e) {
        showToast('Erreur réseau');
    }
}

function openCallModal(data) {
    const modal = document.getElementById('callModal');
    const title = document.getElementById('callModalTitle');
    const text = document.getElementById('callModalText');
    const callLink = document.getElementById('callModalLink');

    title.textContent = data.contact_name;
    if (data.has_phone) {
        text.textContent = `Appel vers ${data.phone}`;
        callLink.href = data.tel_url;
        callLink.style.display = 'inline-block';
    } else {
        text.textContent = 'Numéro non renseigné — notification envoyée dans le chat.';
        callLink.style.display = 'none';
    }

    modal.classList.add('visible');
}

function closeCallModal() {
    document.getElementById('callModal')?.classList.remove('visible');
}

document.addEventListener('DOMContentLoaded', () => {
    refreshCsrfToken();
    loadConversations();
    conversationsPollTimer = setInterval(loadConversations, 15000);

    document.getElementById('searchInput')?.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        document.querySelectorAll('.user-item').forEach((item) => {
            item.style.display = item.textContent.toLowerCase().includes(term) ? 'flex' : 'none';
        });
    });

    document.getElementById('callBtn')?.addEventListener('click', initiateCall);
    document.getElementById('callModalClose')?.addEventListener('click', closeCallModal);
    document.getElementById('callModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'callModal') closeCallModal();
    });

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && selectedUserId) {
            loadMessages(selectedUserId, false);
            loadConversations();
        }
    });
});
