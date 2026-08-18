let selectedUserId = null;
let selectedContact = null;
let messagePollTimer = null;
let conversationsPollTimer = null;
let sendInFlight = false;
let messagesRequestId = 0;
let messagesAbort = null;
let conversationsRequestId = 0;
let conversationsAbort = null;
let knownMessageIds = new Set();
let lastMessagesFingerprint = '';
let lastConversationsFingerprint = '';
let lastUnreadTotal = Number(sessionStorage.getItem('mwinda_msg_unread') || 0);
let msgAudioCtx = null;
let unreadSoundReady = false;

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

function unlockMessageAudio() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        if (!msgAudioCtx) msgAudioCtx = new AudioContext();
        if (msgAudioCtx.state === 'suspended') msgAudioCtx.resume();
    } catch (e) {
        // ignore
    }
}

function playMessageSound() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        if (!msgAudioCtx) msgAudioCtx = new AudioContext();
        if (msgAudioCtx.state === 'suspended') msgAudioCtx.resume();

        const now = msgAudioCtx.currentTime;
        const master = msgAudioCtx.createGain();
        master.connect(msgAudioCtx.destination);
        master.gain.setValueAtTime(0.0001, now);
        master.gain.exponentialRampToValueAtTime(0.5, now + 0.02);
        master.gain.exponentialRampToValueAtTime(0.0001, now + 0.95);

        const pattern = [
            { t: 0, freq: 880, dur: 0.14 },
            { t: 0.18, freq: 1175, dur: 0.14 },
            { t: 0.36, freq: 1319, dur: 0.2 },
            { t: 0.62, freq: 988, dur: 0.26 },
        ];
        pattern.forEach(({ t, freq, dur }) => {
            const osc = msgAudioCtx.createOscillator();
            const gain = msgAudioCtx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(freq, now + t);
            gain.gain.setValueAtTime(0.0001, now + t);
            gain.gain.exponentialRampToValueAtTime(0.32, now + t + 0.012);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + t + dur);
            osc.connect(gain);
            gain.connect(master);
            osc.start(now + t);
            osc.stop(now + t + dur + 0.02);
        });
    } catch (e) {
        // Navigateur sans WebAudio
    }
}

let msgNagTimer = null;
const MSG_NAG_MS = 60 * 1000;

function setMessageNagging(active) {
    if (active) {
        if (!msgNagTimer) {
            msgNagTimer = setInterval(() => {
                if (lastUnreadTotal > 0) playMessageSound();
            }, MSG_NAG_MS);
        }
    } else if (msgNagTimer) {
        clearInterval(msgNagTimer);
        msgNagTimer = null;
    }
}

function totalUnreadCount(conversations) {
    return (conversations || []).reduce((sum, item) => sum + (Number(item.unread_count) || 0), 0);
}

function maybePlayUnreadSound(conversations) {
    const total = totalUnreadCount(conversations);
    if (unreadSoundReady && total > lastUnreadTotal) {
        playMessageSound();
    } else if (unreadSoundReady && total > 0 && lastUnreadTotal === 0) {
        playMessageSound();
    }
    unreadSoundReady = true;
    lastUnreadTotal = total;
    sessionStorage.setItem('mwinda_msg_unread', String(total));
    setMessageNagging(total > 0);
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
    if (conversationsAbort) {
        conversationsAbort.abort();
        conversationsAbort = null;
    }
}

function renderAvatar(data, className = 'user-avatar') {
    if (data.avatar_url) {
        return `<div class="${className}"><img src="${escapeHtml(data.avatar_url)}" alt=""></div>`;
    }
    const initial = data.initial || (data.name || data.username || '?').charAt(0).toUpperCase();
    return `<div class="${className}">${escapeHtml(initial)}</div>`;
}

function todayDateKey() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function yesterdayDateKey() {
    const now = new Date();
    now.setDate(now.getDate() - 1);
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function formatDateLabel(dateKey) {
    if (!dateKey) return '';
    if (dateKey === todayDateKey()) return "Aujourd'hui";
    if (dateKey === yesterdayDateKey()) return 'Hier';
    const [year, month, day] = dateKey.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString('fr-FR', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
    });
}

function renderDateSeparator(dateKey) {
    const label = formatDateLabel(dateKey);
    if (!label) return '';
    return `
        <div class="message-date-separator" data-date-key="${escapeHtml(dateKey)}">
            <span>${escapeHtml(label)}</span>
        </div>
    `;
}

function getLastDateKeyInContainer(container) {
    if (!container) return null;
    const separators = container.querySelectorAll('.message-date-separator[data-date-key]');
    if (!separators.length) return null;
    return separators[separators.length - 1].getAttribute('data-date-key');
}

function renderReadTicks(msg) {
    if (!msg.is_sent) return '';
    const read = Boolean(msg.is_read);
    const title = read ? 'Vu' : 'Envoyé';
    const cls = read ? 'msg-ticks read' : 'msg-ticks sent';
    const svg = `
        <svg viewBox="0 0 16 11" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M11.07 0.75L5.4 6.9 2.85 4.45 1.7 5.6l3.7 3.7 6.85-7.4z"/>
            <path fill="currentColor" d="M14.55 0.75L8.88 6.9 8.1 6.15 6.95 7.3l1.93 1.95 6.85-7.4z"/>
        </svg>`;
    return `<span class="${cls}" title="${title}">${svg}</span>`;
}

function renderMessage(msg) {
    const messageClass = msg.is_sent ? 'sent' : 'received';
    const callClass = msg.message_type === 'call' ? ' call' : '';
    const idAttr = msg.id != null ? ` data-message-id="${msg.id}"` : '';
    const pendingAttr = msg.pending ? ' data-pending="1"' : '';
    const readAttr = msg.is_sent ? ` data-is-read="${msg.is_read ? '1' : '0'}"` : '';
    const ticks = renderReadTicks(msg);
    return `
        <div class="message ${messageClass}${callClass}"${idAttr}${pendingAttr}${readAttr}>
            <div class="message-body">
                <div class="message-bubble">${escapeHtml(msg.content)}</div>
                <div class="message-meta">
                    <span class="message-time">${escapeHtml(msg.time_short || msg.created_at || '')}</span>
                    ${ticks}
                </div>
            </div>
        </div>
    `;
}

function scrollMessagesToBottom({ force = false } = {}) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (force || distanceFromBottom < 80) {
        container.scrollTop = container.scrollHeight;
    }
}

function appendMessage(msg, { forceScroll = true } = {}) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    if (msg.id != null) {
        if (knownMessageIds.has(msg.id)) return;
        knownMessageIds.add(msg.id);
        if (container.querySelector(`[data-message-id="${msg.id}"]`)) return;
    }

    const empty = container.querySelector('.empty-state');
    if (empty) empty.remove();

    const dateKey = msg.date_key || todayDateKey();
    const lastDateKey = getLastDateKeyInContainer(container);
    let html = '';
    if (dateKey !== lastDateKey) {
        html += renderDateSeparator(dateKey);
    }
    html += renderMessage(msg);
    container.insertAdjacentHTML('beforeend', html);
    scrollMessagesToBottom({ force: forceScroll });
}

function updateReadTicks(messages) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;
    (messages || []).forEach((msg) => {
        if (!msg.is_sent || msg.id == null) return;
        const node = container.querySelector(`[data-message-id="${msg.id}"]`);
        if (!node) return;
        const next = msg.is_read ? '1' : '0';
        if (node.getAttribute('data-is-read') === next) return;
        node.setAttribute('data-is-read', next);
        const meta = node.querySelector('.message-meta');
        if (!meta) return;
        const oldTicks = meta.querySelector('.msg-ticks');
        if (oldTicks) oldTicks.remove();
        meta.insertAdjacentHTML('beforeend', renderReadTicks(msg));
    });
}

function messagesFingerprint(messages) {
    return (messages || [])
        .map((msg) => `${msg.id || 'x'}:${msg.is_read ? 1 : 0}:${msg.content || ''}`)
        .join('|');
}

function conversationsFingerprint(conversations) {
    return (conversations || [])
        .map((c) => `${c.id}:${c.last_activity_ts || 0}:${c.unread_count || 0}:${c.last_message || ''}`)
        .join('|');
}

function clearContactUnreadBadge(userId) {
    const item = document.querySelector(`.user-item[data-user-id="${userId}"]`);
    if (!item) return;
    const badge = item.querySelector('.unread-badge');
    if (!badge) return;
    badge.classList.remove('visible');
    badge.textContent = '';
}

function syncHeaderMessageUnread(previousMessageUnread, nextMessageUnread) {
    // Ajuste discrètement le badge cloche sans toucher au reste de l’UI.
    const badge = document.getElementById('notifBadge');
    if (!badge) return;
    const current = Number(badge.textContent || 0);
    const prev = Number(previousMessageUnread) || 0;
    const next = Number(nextMessageUnread) || 0;
    const delta = prev - next;
    if (delta <= 0) return;
    const updated = Math.max(0, current - delta);
    badge.textContent = String(updated);
    badge.classList.toggle('visible', updated > 0);
    sessionStorage.setItem('mwinda_notif_unread', String(updated));
    if (updated === 0) {
        document.getElementById('notifBell')?.classList.remove('is-nagging');
    }
}

function renderMessages(messages, { soft = false } = {}) {
    const container = document.getElementById('messagesContainer');
    if (!container) return;

    const list = messages || [];
    const fingerprint = messagesFingerprint(list);
    if (soft && fingerprint === lastMessagesFingerprint) {
        return;
    }

    const previousIds = knownMessageIds;
    const isRefresh = soft && previousIds.size > 0;

    if (isRefresh) {
        const newIncoming = list.filter(
            (msg) => msg.id != null && !previousIds.has(msg.id),
        );
        updateReadTicks(list);
        newIncoming.forEach((msg) => appendMessage(msg, { forceScroll: !msg.is_sent }));
        knownMessageIds = new Set(list.filter((msg) => msg.id != null).map((msg) => msg.id));
        lastMessagesFingerprint = fingerprint;
        if (newIncoming.length && selectedUserId) {
            const last = newIncoming[newIncoming.length - 1];
            const preview = last.message_type === 'call' ? '📞 Appel' : (last.content || '');
            updateConversationPreview(selectedUserId, preview);
        }
        return;
    }

    knownMessageIds = new Set(list.filter((msg) => msg.id != null).map((msg) => msg.id));
    lastMessagesFingerprint = fingerprint;

    if (!list.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💬</div>
                Aucun message. Écrivez le premier message ou lancez un appel.
            </div>`;
        return;
    }
    let html = '';
    let lastDateKey = null;
    list.forEach((msg) => {
        const dateKey = msg.date_key || null;
        if (dateKey && dateKey !== lastDateKey) {
            html += renderDateSeparator(dateKey);
            lastDateKey = dateKey;
        }
        html += renderMessage(msg);
    });
    container.innerHTML = html;
    scrollMessagesToBottom({ force: true });
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
    title.textContent = contact.short_name || contact.name || contact.username;
    const titleBits = [contact.title || contact.role, contact.branch].filter(Boolean);
    subtitle.textContent = `${titleBits.join(' · ')}${contact.phone ? ' · ' + contact.phone : ''}`;
    callBtn.disabled = false;
}

function loadConversations() {
    const requestId = ++conversationsRequestId;
    if (conversationsAbort) conversationsAbort.abort();
    conversationsAbort = new AbortController();

    const separator = window.MESSAGING_URLS.conversations.includes('?') ? '&' : '?';
    const conversationsUrl = `${window.MESSAGING_URLS.conversations}${separator}_ts=${Date.now()}`;

    return fetch(conversationsUrl, {
        credentials: 'same-origin',
        signal: conversationsAbort.signal,
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
            if (requestId !== conversationsRequestId) return;
            const conversations = data.conversations || [];
            maybePlayUnreadSound(conversations);
            renderConversations(conversations);
            return conversations;
        })
        .catch((error) => {
            if (error.name === 'AbortError') return;
            if (error.message === 'auth') return;
            console.error('Conversations error:', error);
            const list = document.getElementById('usersList');
            if (list && !list.querySelector('.user-item')) {
                list.innerHTML = '<div class="empty-state">Impossible de charger les contacts. Rechargez la page.</div>';
            }
            return [];
        });
}

function buildConversationItemHtml(conversation) {
    return `
        ${renderAvatar(conversation)}
        <div class="user-info">
            <h3>${escapeHtml(conversation.short_name || conversation.name)}</h3>
            <p class="user-meta">${escapeHtml(conversation.title || conversation.branch || '')}</p>
            <p class="user-preview">${escapeHtml(conversation.last_message)}</p>
        </div>
        <div class="unread-badge ${conversation.unread_count > 0 ? 'visible' : ''}">
            ${conversation.unread_count > 0 ? conversation.unread_count : ''}
        </div>
    `;
}

function applyConversationDataToItem(item, conversation) {
    if (!item) return;

    const currentTitle = item.querySelector('.user-info h3')?.textContent || '';
    const nextTitle = conversation.short_name || conversation.name || '';
    const currentMeta = item.querySelector('.user-meta')?.textContent || '';
    const nextMeta = conversation.title || conversation.branch || '';
    const previewEl = item.querySelector('.user-preview');
    const currentPreview = previewEl?.textContent || '';
    const nextPreview = conversation.last_message || '';
    const badge = item.querySelector('.unread-badge');
    const currentUnread = badge && badge.classList.contains('visible')
        ? Number(badge.textContent || 0)
        : 0;
    const nextUnread = Number(conversation.unread_count) || 0;

    if (currentTitle !== nextTitle) {
        const titleEl = item.querySelector('.user-info h3');
        if (titleEl) titleEl.textContent = nextTitle;
    }
    if (currentMeta !== nextMeta) {
        const metaEl = item.querySelector('.user-meta');
        if (metaEl) metaEl.textContent = nextMeta;
    }
    if (currentPreview !== nextPreview && previewEl) {
        previewEl.textContent = nextPreview;
    }
    if (badge && currentUnread !== nextUnread) {
        if (nextUnread > 0) {
            badge.classList.add('visible');
            badge.textContent = String(nextUnread);
        } else {
            badge.classList.remove('visible');
            badge.textContent = '';
        }
    }
    item.dataset.activityTs = String(conversation.last_activity_ts || 0);
}

function renderConversations(conversations) {
    const list = document.getElementById('usersList');
    if (!list) return;

    if (!conversations.length) {
        list.innerHTML = '<div class="empty-state">Aucun collègue disponible</div>';
        lastConversationsFingerprint = '';
        return;
    }

    const fingerprint = conversationsFingerprint(conversations);
    if (fingerprint === lastConversationsFingerprint) {
        return;
    }
    lastConversationsFingerprint = fingerprint;

    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    const expectedIds = new Set(conversations.map((conversation) => String(conversation.id)));

    list.querySelectorAll('.user-item').forEach((node) => {
        if (!expectedIds.has(node.dataset.userId)) {
            node.remove();
        }
    });

    // Met à jour le contenu sans bouger les nodes d’abord.
    conversations.forEach((conversation) => {
        const idStr = String(conversation.id);
        let item = list.querySelector(`.user-item[data-user-id="${idStr}"]`);

        if (!item) {
            item = document.createElement('div');
            item.className = 'user-item';
            item.dataset.userId = idStr;
            item.onclick = (event) => openUserChat(conversation.id, event);
            item.innerHTML = buildConversationItemHtml(conversation);
            item.dataset.activityTs = String(conversation.last_activity_ts || 0);
            list.appendChild(item);
        } else {
            applyConversationDataToItem(item, conversation);
        }
    });

    // Réordonne seulement si l’ordre a changé (dernier échange en haut).
    const desiredOrder = conversations.map((c) => String(c.id)).join(',');
    const currentOrder = [...list.querySelectorAll('.user-item')].map((n) => n.dataset.userId).join(',');
    if (desiredOrder !== currentOrder) {
        const fragment = document.createDocumentFragment();
        conversations.forEach((conversation) => {
            const item = list.querySelector(`.user-item[data-user-id="${conversation.id}"]`);
            if (item) fragment.appendChild(item);
        });
        list.appendChild(fragment);
    }

    if (selectedUserId) {
        const active = list.querySelector(`[data-user-id="${selectedUserId}"]`);
        if (active) active.classList.add('active');
    }
}

function openUserChat(userId, event) {
    unlockMessageAudio();
    selectedUserId = Number(userId);
    knownMessageIds = new Set();
    lastMessagesFingerprint = '';
    document.querySelectorAll('.user-item').forEach((item) => item.classList.remove('active'));
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
        const badge = event.currentTarget.querySelector('.unread-badge');
        if (badge) {
            badge.classList.remove('visible');
            badge.textContent = '';
        }
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

    const soft = !focusInput && knownMessageIds.size > 0;

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
            if (requestId !== messagesRequestId || Number(selectedUserId) !== targetId) {
                return;
            }
            selectedContact = data.contact;
            updateChatHeader(data.contact);
            renderMessages(data.messages || [], { soft });
            clearContactUnreadBadge(targetId);

            const unreadTotal = Number(data.unread_total);
            if (!Number.isNaN(unreadTotal)) {
                const previousMessageUnread = lastUnreadTotal;
                lastUnreadTotal = unreadTotal;
                sessionStorage.setItem('mwinda_msg_unread', String(unreadTotal));
                setMessageNagging(unreadTotal > 0);
                syncHeaderMessageUnread(previousMessageUnread, unreadTotal);
            }

            if (focusInput) {
                const input = document.getElementById('messageInput');
                input?.focus();
                autoResizeMessageInput(input);
                // Une seule synchro liste après ouverture — pas à chaque poll.
                loadConversations();
            }
        })
        .catch((error) => {
            if (error.name === 'AbortError' || error.message === 'auth') return;
            if (requestId !== messagesRequestId) return;
            if (!soft) {
                document.getElementById('messagesContainer').innerHTML =
                    '<div class="empty-state">Erreur de chargement des messages</div>';
            }
        });
}

function startMessagePolling() {
    if (messagePollTimer) clearInterval(messagePollTimer);
    // Poll plus lent = moins de “refresh” visible ; le soft skip évite le DOM inutile.
    messagePollTimer = setInterval(() => {
        if (selectedUserId) loadMessages(selectedUserId, false);
    }, 8000);
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        event.stopPropagation();
        sendMessage(event);
    }
}

function autoResizeMessageInput(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 72)}px`;
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
    const list = document.getElementById('usersList');
    const item = list?.querySelector(`.user-item[data-user-id="${userId}"]`);
    if (!item || !list) return;
    const previewEl = item.querySelector('.user-preview');
    if (previewEl) previewEl.textContent = preview;
    item.dataset.activityTs = String(Math.floor(Date.now() / 1000));
    if (list.firstElementChild !== item) {
        list.prepend(item);
    }
    // Invalide le cache pour accepter le nouvel ordre serveur au prochain poll.
    lastConversationsFingerprint = '';
}

function removePendingOptimisticMessages() {
    const container = document.getElementById('messagesContainer');
    if (!container) return;
    container.querySelectorAll('.message[data-pending="1"]').forEach((node) => node.remove());
}

async function sendMessage(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    if (!selectedUserId) {
        showToast('Sélectionnez un contact d\'abord');
        return;
    }
    if (sendInFlight) return;

    unlockMessageAudio();
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.querySelector('#messageForm .chat-send-btn');
    const content = (messageInput?.value || '').trim();
    if (!content) return;

    sendInFlight = true;
    if (sendBtn) sendBtn.disabled = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Aperçu local unique (marqué pending) — remplacé par la réponse serveur.
    const container = document.getElementById('messagesContainer');
    if (container) {
        const empty = container.querySelector('.empty-state');
        if (empty) empty.remove();
        container.insertAdjacentHTML(
            'beforeend',
            (() => {
                const dateKey = todayDateKey();
                const lastDateKey = getLastDateKeyInContainer(container);
                let html = '';
                if (dateKey !== lastDateKey) html += renderDateSeparator(dateKey);
                html += renderMessage({
                    content,
                    is_sent: true,
                    is_read: false,
                    pending: true,
                    message_type: 'text',
                    date_key: dateKey,
                    time_short: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
                });
                return html;
            })(),
        );
        scrollMessagesToBottom({ force: true });
    }
    updateConversationPreview(selectedUserId, content);

    const formData = new FormData();
    formData.append('content', content);

    try {
        const data = await postWithCsrf(
            urlForUser(window.MESSAGING_URLS.send, selectedUserId),
            formData,
        );
        removePendingOptimisticMessages();
        if (data.ok && data.message) {
            appendMessage(data.message, { forceScroll: true });
            updateConversationPreview(selectedUserId, data.message.content);
            lastMessagesFingerprint = '';
            // Pas de reload immédiat : évite un 2e affichage / flash.
        } else if (data.error) {
            showToast(data.error);
            loadMessages(selectedUserId, false);
        }
    } catch (e) {
        removePendingOptimisticMessages();
        showToast('Erreur lors de l\'envoi');
        // Remet le texte pour ne pas perdre le message
        if (messageInput && !messageInput.value) messageInput.value = content;
        loadMessages(selectedUserId, false);
    } finally {
        sendInFlight = false;
        if (sendBtn) sendBtn.disabled = false;
        messageInput?.focus();
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
    const initialUserId = Number(new URLSearchParams(window.location.search).get('user') || 0);
    loadConversations().then(() => {
        if (!initialUserId || selectedUserId) return;
        const item = document.querySelector(`.user-item[data-user-id="${initialUserId}"]`);
        if (!item) return;
        openUserChat(initialUserId, { currentTarget: item });
        const url = new URL(window.location.href);
        url.searchParams.delete('user');
        window.history.replaceState({}, '', url.toString());
    });
    conversationsPollTimer = setInterval(loadConversations, 20000);

    document.addEventListener('click', unlockMessageAudio, { once: true });
    document.addEventListener('keydown', unlockMessageAudio, { once: true });

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
