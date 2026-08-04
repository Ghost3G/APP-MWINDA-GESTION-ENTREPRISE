const boardState = {
    tasks: window.TASK_BOARD?.tasks || [],
    columns: window.TASK_BOARD?.columns || { pending: [], in_progress: [], done: [] },
    labels: window.TASK_BOARD?.labels || [],
    members: window.TASK_BOARD?.members || [],
    viewMode: window.TASK_BOARD?.viewMode || 'board',
    calendarDate: new Date(),
    draggedTaskId: null,
};

function urlFor(template, id) {
    return template.replace(/\/0(\/|$)/, `/${id}$1`);
}

function getCsrfToken() {
    if (window.TASK_BOARD?.csrfToken) {
        return window.TASK_BOARD.csrfToken;
    }
    const input = document.querySelector('#createCardForm input[name="csrfmiddlewaretoken"]');
    if (input?.value) {
        return input.value;
    }
    return getCookie('csrftoken');
}

function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (const cookie of cookies) {
        const trimmed = cookie.trim();
        if (trimmed.startsWith(name + '=')) {
            return decodeURIComponent(trimmed.substring(name.length + 1));
        }
    }
    return '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}

function showToast(message) {
    const toast = document.getElementById('boardToast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'board-toast visible';
    setTimeout(() => { toast.className = 'board-toast'; }, 2800);
}

function renderMemberAvatars(members, limit = 3) {
    const slice = (members || []).slice(0, limit);
    return slice.map((member) => {
        if (member.avatar_url) {
            return `<span class="kanban-member" title="${escapeHtml(member.name)}"><img src="${escapeHtml(member.avatar_url)}" alt=""></span>`;
        }
        return `<span class="kanban-member" title="${escapeHtml(member.name)}">${escapeHtml(member.initial || '?')}</span>`;
    }).join('');
}

function boardIcon(name) {
    const src = window.TASK_BOARD?.icons?.[name] || '';
    return src ? `<img src="${escapeHtml(src)}" alt="" class="board-meta-icon">` : '';
}

function renderCard(task) {
    const labels = (task.labels || []).map((label) =>
        `<span class="kanban-label" style="background:${escapeHtml(label.color)}">${escapeHtml(label.name)}</span>`
    ).join('');

    const dueClass = task.is_overdue ? 'overdue' : '';
    const dueHtml = task.due_date_label
        ? `<span class="kanban-card-due ${dueClass}">${boardIcon('calendar')} ${escapeHtml(task.due_date_label)}</span>`
        : '<span></span>';

    const icons = [];
    if (task.comments_count) icons.push(`<span class="kanban-card-icon-item">${boardIcon('comment')} ${task.comments_count}</span>`);
    if (task.attachments_count) icons.push(`<span class="kanban-card-icon-item">${boardIcon('attachment')} ${task.attachments_count}</span>`);
    if (task.checklist_progress && task.checklist_progress !== '0/0') {
        icons.push(`<span class="kanban-card-icon-item">${boardIcon('checklist')} ${task.checklist_progress}</span>`);
    }

    return `
        <article class="kanban-card" draggable="true" data-task-id="${task.id}">
            ${labels ? `<div class="kanban-card-labels">${labels}</div>` : ''}
            <h4 class="kanban-card-title">${escapeHtml(task.title)}</h4>
            <div class="kanban-card-meta">
                <div class="kanban-card-members">${renderMemberAvatars(task.members)}</div>
                ${dueHtml}
            </div>
            ${icons.length ? `<div class="kanban-card-icons">${icons.join('')}</div>` : ''}
        </article>
    `;
}

function renderBoard() {
    ['pending', 'in_progress', 'done'].forEach((status) => {
        const column = document.getElementById(`column-${status}`);
        const count = document.getElementById(`count-${status}`);
        const tasks = boardState.columns[status] || [];
        if (column) column.innerHTML = tasks.map(renderCard).join('');
        if (count) count.textContent = tasks.length;
    });
    bindCardEvents();
}

function bindCardEvents() {
    document.querySelectorAll('.kanban-card').forEach((card) => {
        card.addEventListener('click', () => openCardModal(card.dataset.taskId));
        card.addEventListener('dragstart', (event) => {
            boardState.draggedTaskId = card.dataset.taskId;
            card.classList.add('dragging');
            event.dataTransfer.effectAllowed = 'move';
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            boardState.draggedTaskId = null;
        });
    });

    document.querySelectorAll('.kanban-cards').forEach((zone) => {
        zone.addEventListener('dragover', (event) => {
            event.preventDefault();
            zone.classList.add('drag-over');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
        zone.addEventListener('drop', async (event) => {
            event.preventDefault();
            zone.classList.remove('drag-over');
            const taskId = boardState.draggedTaskId;
            const newStatus = zone.dataset.status;
            if (!taskId || !newStatus) return;
            await updateTaskStatus(taskId, newStatus);
        });
    });
}

async function updateTaskStatus(taskId, status) {
    const formData = new FormData();
    formData.append('status', status);
    formData.append('csrfmiddlewaretoken', getCsrfToken());

    const response = await fetch(urlFor(window.TASK_BOARD.urls.status, taskId), {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const data = await response.json();
    if (!data.ok) {
        showToast(data.error || 'Erreur de déplacement');
        return;
    }
    refreshColumnsFromTask(data.task);
    renderBoard();
    if (boardState.viewMode === 'calendar') renderCalendar();
    if (boardState.viewMode === 'timeline') renderTimeline();
}

function refreshColumnsFromTask(task) {
    ['pending', 'in_progress', 'done'].forEach((status) => {
        boardState.columns[status] = (boardState.columns[status] || []).filter((item) => item.id !== task.id);
    });
    if (!boardState.columns[task.status]) boardState.columns[task.status] = [];
    boardState.columns[task.status].push(task);

    const index = boardState.tasks.findIndex((item) => item.id === task.id);
    if (index >= 0) boardState.tasks[index] = task;
    else boardState.tasks.push(task);
}

async function openCardModal(taskId) {
    const modal = document.getElementById('cardModal');
    const body = document.getElementById('cardModalBody');
    if (!modal || !body) return;

    modal.classList.add('visible');
    body.innerHTML = '<p class="board-modal-loading">Chargement...</p>';

    const response = await fetch(urlFor(window.TASK_BOARD.urls.detail, taskId));
    const data = await response.json();
    if (!data.ok) {
        body.innerHTML = '<p>Impossible de charger la carte.</p>';
        return;
    }
    body.innerHTML = renderCardModal(data.task);
    bindModalEvents(data.task);
}

function renderCardModal(task) {
    const labelOptions = boardState.labels.map((label) => {
        const checked = (task.label_ids || []).includes(label.id) ? 'checked' : '';
        return `
            <label class="board-label-option" style="border-color:${label.color}55">
                <input type="checkbox" name="label_ids" value="${label.id}" ${checked}>
                <span style="color:${label.color}">${escapeHtml(label.name)}</span>
            </label>`;
    }).join('');

    const memberOptions = boardState.members.map((member) => {
        const checked = (task.member_ids || []).includes(member.id) ? 'checked' : '';
        return `
            <label class="board-member-option">
                <input type="checkbox" name="member_ids" value="${member.id}" ${checked}>
                <span>${escapeHtml(member.name)}</span>
            </label>`;
    }).join('');

    const comments = (task.comments || []).map((comment) => `
        <div class="board-comment">
            <strong>${escapeHtml(comment.author.name)} · ${escapeHtml(comment.created_at)}</strong>
            <p>${escapeHtml(comment.content)}</p>
        </div>
    `).join('') || '<p style="color:#71717a;font-size:13px;">Aucun commentaire</p>';

    const checklists = (task.checklists || []).map((checklist) => {
        const items = (checklist.items || []).map((item) => `
            <label class="board-checklist-item ${item.is_done ? 'done' : ''}">
                <input type="checkbox" data-item-id="${item.id}" ${item.is_done ? 'checked' : ''}>
                <span>${escapeHtml(item.text)}</span>
            </label>
        `).join('');
        return `
            <div class="board-checklist-block" data-checklist-id="${checklist.id}">
                <strong>${escapeHtml(checklist.title)} (${escapeHtml(checklist.progress)})</strong>
                ${items}
                <form class="board-inline-form checklist-item-form" data-checklist-id="${checklist.id}">
                    <input type="text" name="text" placeholder="Ajouter un élément..." required>
                    <button type="submit" class="board-mini-btn">+</button>
                </form>
            </div>`;
    }).join('');

    const attachments = (task.attachments || []).map((file) => `
        <div class="board-attachment">
            <a href="${escapeHtml(file.url)}" target="_blank" rel="noopener">${escapeHtml(file.name)}</a>
            <span>${escapeHtml(file.uploaded_by.name)}</span>
        </div>
    `).join('') || '<p style="color:#71717a;font-size:13px;">Aucune pièce jointe</p>';

    return `
        <form id="cardDetailForm" data-task-id="${task.id}">
            <input class="board-detail-title" name="title" value="${escapeHtml(task.title)}">
            <div class="board-detail-grid">
                <div>
                    <div class="board-form-group">
                        <label>Description</label>
                        <textarea name="description" rows="4" placeholder="Détails de la carte...">${escapeHtml(task.description || '')}</textarea>
                    </div>

                    <div class="board-section">
                        <h4>Commentaires</h4>
                        ${comments}
                        <form class="board-inline-form" id="commentForm" data-task-id="${task.id}">
                            <input type="text" name="content" placeholder="Écrire un commentaire..." required>
                            <button type="submit" class="board-mini-btn">➤</button>
                        </form>
                    </div>

                    <div class="board-section">
                        <h4>Listes de contrôle</h4>
                        ${checklists || '<p style="color:#71717a;font-size:13px;">Aucune liste de contrôle</p>'}
                        <form class="board-inline-form" id="checklistForm" data-task-id="${task.id}">
                            <input type="text" name="title" placeholder="Nouvelle liste de contrôle..." required>
                            <button type="submit" class="board-mini-btn">+</button>
                        </form>
                    </div>

                    <div class="board-section">
                        <h4>Pièces jointes</h4>
                        ${attachments}
                        <form class="board-inline-form" id="attachmentForm" data-task-id="${task.id}" enctype="multipart/form-data">
                            <input type="file" name="file" required>
                            <button type="submit" class="board-mini-btn board-attach-btn" title="Joindre un fichier">${boardIcon('attachment')}</button>
                        </form>
                    </div>
                </div>

                <aside>
                    <div class="board-form-group">
                        <label>Échéance</label>
                        <input type="date" name="due_date" value="${escapeHtml(task.due_date || '')}">
                    </div>
                    <div class="board-form-group">
                        <label>Étiquettes</label>
                        <div class="board-label-options">${labelOptions}</div>
                    </div>
                    <div class="board-form-group">
                        <label>Membres</label>
                        <div class="board-member-options">${memberOptions}</div>
                    </div>
                    <div class="board-form-group">
                        <label>Statut</label>
                        <p style="margin:0;color:#fde047;font-weight:700;">${escapeHtml(task.status_label)}</p>
                    </div>
                    <button type="submit" class="board-primary-btn" style="width:100%;">Enregistrer</button>
                </aside>
            </div>
        </form>
    `;
}

function bindModalEvents(task) {
    const form = document.getElementById('cardDetailForm');
    form?.addEventListener('submit', async (event) => {
        event.preventDefault();
        await saveCardDetails(task.id, new FormData(form));
    });

    document.getElementById('commentForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const commentForm = event.currentTarget;
        const formData = new FormData(commentForm);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        const response = await fetch(urlFor(window.TASK_BOARD.urls.comment, task.id), {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (data.ok) {
            commentForm.reset();
            openCardModal(task.id);
        }
    });

    document.getElementById('checklistForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const checklistForm = event.currentTarget;
        const formData = new FormData(checklistForm);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        const response = await fetch(urlFor(window.TASK_BOARD.urls.checklist, task.id), {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (data.ok) openCardModal(task.id);
    });

    document.querySelectorAll('.checklist-item-form').forEach((itemForm) => {
        itemForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const checklistId = itemForm.dataset.checklistId;
            const formData = new FormData(itemForm);
            formData.append('csrfmiddlewaretoken', getCsrfToken());
            const response = await fetch(urlFor(window.TASK_BOARD.urls.checklistItem, checklistId), {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (data.ok) openCardModal(task.id);
        });
    });

    document.querySelectorAll('.board-checklist-item input[type="checkbox"]').forEach((checkbox) => {
        checkbox.addEventListener('change', async () => {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());
            await fetch(urlFor(window.TASK_BOARD.urls.toggleItem, checkbox.dataset.itemId), {
                method: 'POST',
                body: formData,
            });
            openCardModal(task.id);
        });
    });

    document.getElementById('attachmentForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const attachmentForm = event.currentTarget;
        const formData = new FormData(attachmentForm);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        const response = await fetch(urlFor(window.TASK_BOARD.urls.attachment, task.id), {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (data.ok) {
            attachmentForm.reset();
            openCardModal(task.id);
        } else {
            showToast(data.error || 'Erreur upload');
        }
    });
}

async function saveCardDetails(taskId, formData) {
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    const response = await fetch(urlFor(window.TASK_BOARD.urls.update, taskId), {
        method: 'POST',
        body: formData,
    });
    const data = await response.json();
    if (!data.ok) {
        showToast(data.error || 'Erreur de sauvegarde');
        return;
    }
    refreshColumnsFromTask(data.task);
    renderBoard();
    showToast('Carte enregistrée');
    openCardModal(taskId);
}

function switchView(view) {
    boardState.viewMode = view;
    document.getElementById('viewModeInput').value = view;
    document.querySelectorAll('.board-view-tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.view === view);
    });
    document.querySelectorAll('.board-view').forEach((section) => section.classList.add('hidden'));
    if (view === 'board') document.getElementById('boardView')?.classList.remove('hidden');
    if (view === 'calendar') {
        document.getElementById('calendarView')?.classList.remove('hidden');
        renderCalendar();
    }
    if (view === 'timeline') {
        document.getElementById('timelineView')?.classList.remove('hidden');
        renderTimeline();
    }
}

function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    const title = document.getElementById('calendarTitle');
    if (!grid || !title) return;

    const current = boardState.calendarDate;
    const year = current.getFullYear();
    const month = current.getMonth();
    const monthLabel = current.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
    title.textContent = monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);

    const firstDay = new Date(year, month, 1);
    const startOffset = (firstDay.getDay() + 6) % 7;
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const weekdays = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
    let html = weekdays.map((day) => `<div class="calendar-weekday">${day}</div>`).join('');

    for (let i = 0; i < startOffset; i += 1) {
        html += '<div class="calendar-day other-month"></div>';
    }

    const today = new Date();
    for (let day = 1; day <= daysInMonth; day += 1) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const dayTasks = boardState.tasks.filter((task) => task.due_date === dateStr);
        const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
        html += `
            <div class="calendar-day ${isToday ? 'today' : ''}">
                <div class="calendar-day-number">${day}</div>
                ${dayTasks.map((task) => `<button type="button" class="calendar-task" data-task-id="${task.id}">${escapeHtml(task.title)}</button>`).join('')}
            </div>`;
    }

    grid.innerHTML = html;
    grid.querySelectorAll('.calendar-task').forEach((button) => {
        button.addEventListener('click', () => openCardModal(button.dataset.taskId));
    });
}

function renderTimeline() {
    const list = document.getElementById('timelineList');
    if (!list) return;

    const sorted = [...boardState.tasks].sort((a, b) => {
        const aDate = a.due_date || a.created_at;
        const bDate = b.due_date || b.created_at;
        return aDate.localeCompare(bDate);
    });

    if (!sorted.length) {
        list.innerHTML = '<div class="board-empty-state"><p>Aucune tâche à afficher sur la chronologie.</p></div>';
        return;
    }

    list.innerHTML = sorted.map((task) => {
        const start = task.created_at_label;
        const end = task.due_date_label || 'Sans échéance';
        const progress = task.status === 'done' ? 100 : task.status === 'in_progress' ? 60 : 25;
        return `
            <article class="timeline-item" data-task-id="${task.id}">
                <div class="timeline-range">${escapeHtml(start)} → ${escapeHtml(end)}</div>
                <div>
                    <div class="timeline-title">${escapeHtml(task.title)}</div>
                    <div class="timeline-bar-wrap"><div class="timeline-bar" style="width:${progress}%"></div></div>
                </div>
                <div class="timeline-status">${escapeHtml(task.status_label)}</div>
            </article>`;
    }).join('');

    list.querySelectorAll('.timeline-item').forEach((item) => {
        item.addEventListener('click', () => openCardModal(item.dataset.taskId));
    });
}

document.addEventListener('DOMContentLoaded', () => {
    renderBoard();
    if (boardState.viewMode === 'calendar') renderCalendar();
    if (boardState.viewMode === 'timeline') renderTimeline();

    document.querySelectorAll('.board-view-tab').forEach((tab) => {
        tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    document.getElementById('calendarPrev')?.addEventListener('click', () => {
        boardState.calendarDate.setMonth(boardState.calendarDate.getMonth() - 1);
        renderCalendar();
    });
    document.getElementById('calendarNext')?.addEventListener('click', () => {
        boardState.calendarDate.setMonth(boardState.calendarDate.getMonth() + 1);
        renderCalendar();
    });

    document.getElementById('closeCardModal')?.addEventListener('click', () => {
        document.getElementById('cardModal')?.classList.remove('visible');
    });
    document.getElementById('cardModal')?.addEventListener('click', (event) => {
        if (event.target.id === 'cardModal') document.getElementById('cardModal').classList.remove('visible');
    });

    const createModal = document.getElementById('createCardModal');
    document.getElementById('openCreateCardBtn')?.addEventListener('click', () => createModal?.classList.add('visible'));
    document.getElementById('closeCreateCardModal')?.addEventListener('click', () => createModal?.classList.remove('visible'));
    createModal?.addEventListener('click', (event) => {
        if (event.target.id === 'createCardModal') createModal.classList.remove('visible');
    });

    document.getElementById('createCardForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        const response = await fetch(window.TASK_BOARD.urls.create, {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (!data.ok) {
            showToast(data.error || 'Erreur création');
            return;
        }
        refreshColumnsFromTask(data.task);
        boardState.tasks.push(data.task);
        renderBoard();
        createModal.classList.remove('visible');
        event.currentTarget.reset();
        showToast('Carte créée');
    });
});
