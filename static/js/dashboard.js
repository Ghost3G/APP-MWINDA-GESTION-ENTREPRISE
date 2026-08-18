function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (let i = 0; i < cookies.length; i += 1) {
        const cookie = cookies[i].trim();
        if (cookie.startsWith(name + "=")) {
            return decodeURIComponent(cookie.substring(name.length + 1));
        }
    }
    return "";
}

function formatSeconds(totalSeconds) {
    const safeSeconds = Math.max(totalSeconds, 0);
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const seconds = safeSeconds % 60;
    return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function parseTimerValue(value) {
    if (!value || typeof value !== "string") {
        return 0;
    }
    const parts = value.split(":").map((part) => parseInt(part, 10));
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
        return 0;
    }
    return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
}

function updateNotificationBadges() {
    const messageBadge = document.querySelector('a[href*="messaging"] .notification-badge');
    const projectBadge = document.querySelector('a[href*="projects"] .notification-badge');
    const unreadMessages = parseInt(messageBadge?.textContent || "0", 10);
    const newProjectAssignments = parseInt(projectBadge?.textContent || "0", 10);

    if (messageBadge) {
        if (unreadMessages > 0) {
            messageBadge.textContent = unreadMessages;
            messageBadge.classList.add("visible");
        } else {
            messageBadge.classList.remove("visible");
        }
    }

    if (projectBadge) {
        if (newProjectAssignments > 0) {
            projectBadge.textContent = newProjectAssignments;
            projectBadge.classList.add("visible");
        } else {
            projectBadge.classList.remove("visible");
        }
    }
}

function updateTaskProgress() {
    const openItems = Array.from(document.querySelectorAll('.task-list-panel[data-task-panel="open"] .task-item'));
    const doneItems = Array.from(document.querySelectorAll('.task-list-panel[data-task-panel="done"] .task-item'));
    const progressCircle = document.querySelector(".progress-circle");
    const progressValue = document.querySelector(".progress-value");
    const total = openItems.length + doneItems.length;
    const completedCount = doneItems.length;

    openItems.forEach((taskItem) => {
        taskItem.classList.remove("next");
    });
    const nextTask = openItems.find((taskItem) => taskItem.dataset.taskStatus !== "done");
    if (nextTask) {
        nextTask.classList.add("next");
    }

    const percent = total ? Math.round((completedCount / total) * 100) : 0;
    if (progressCircle) {
        progressCircle.style.setProperty("--progress", percent);
    }
    if (progressValue) {
        progressValue.textContent = percent + "%";
    }
}

document.addEventListener("DOMContentLoaded", function () {
    const config = window.dashboardTimerConfig || {};
    const menuToggle = document.querySelector(".menu-toggle");
    const sidebar = document.querySelector(".sidebar-panel");
    const pauseButton = document.querySelector(".pause-button");
    const taskTimerNode = document.querySelector("#task-timer-row .timer-value");
    const workTimerNode = document.querySelector("#work-timer-row .timer-value");
    const pauseTimerNode = document.querySelector("#pause-timer-row .timer-value");
    const taskItems = Array.from(document.querySelectorAll(".task-item"));

    const state = {
        activeTaskLabel: config.activeTaskLabel || "",
        activeTaskStartedAt: config.activeTaskStartedAt || "",
        activePauseStartedAt: config.activePauseStartedAt || "",
        activeWorkStartedAt: config.activeWorkStartedAt || "",
        isPauseRunning: config.isPauseRunning === true || config.isPauseRunning === "true",
        isWorkRunning: config.isWorkRunning === true || config.isWorkRunning === "true",
        baseTaskSeconds: parseTimerValue(taskTimerNode ? taskTimerNode.textContent : "00:00:00"),
        baseWorkSeconds: parseTimerValue(workTimerNode ? workTimerNode.textContent : "00:00:00"),
        basePauseSeconds: parseTimerValue(pauseTimerNode ? pauseTimerNode.textContent : "00:00:00"),
    };

    function revealNextTaskBatch() {
        // Conservé pour compatibilité — les tâches restent visibles via les onglets.
    }

    function moveTaskToDonePanel(taskItem) {
        const donePanel = document.querySelector('.task-list-panel[data-task-panel="done"]');
        if (!donePanel || !taskItem) {
            return;
        }
        const empty = donePanel.querySelector('.task-empty');
        if (empty) {
            empty.remove();
        }
        taskItem.classList.add('completed');
        taskItem.classList.remove('active', 'task-new', 'next');
        taskItem.dataset.taskStatus = 'done';
        const badge = taskItem.querySelector('.task-new-badge, .task-new-label, .task-new-dot');
        if (badge) {
            badge.remove();
        }
        const leftoverLabel = taskItem.querySelector('.task-new-label');
        if (leftoverLabel) {
            leftoverLabel.remove();
        }
        donePanel.appendChild(taskItem);

        const openPanel = document.querySelector('.task-list-panel[data-task-panel="open"]');
        if (openPanel && !openPanel.querySelector('.task-item') && !openPanel.querySelector('.task-empty')) {
            const p = document.createElement('p');
            p.className = 'task-empty';
            p.textContent = 'Aucune tâche en cours.';
            openPanel.appendChild(p);
        }

        const openTab = document.querySelector('.task-tab[data-task-tab="open"] .task-tab-count');
        const doneTab = document.querySelector('.task-tab[data-task-tab="done"] .task-tab-count');
        if (openTab) {
            openTab.textContent = String(document.querySelectorAll('.task-list-panel[data-task-panel="open"] .task-item').length);
        }
        if (doneTab) {
            doneTab.textContent = String(document.querySelectorAll('.task-list-panel[data-task-panel="done"] .task-item').length);
        }
    }

    function initTaskTabs() {
        const tabs = Array.from(document.querySelectorAll('.task-tab'));
        const panels = Array.from(document.querySelectorAll('.task-list-panel'));
        if (!tabs.length) {
            return;
        }
        tabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                const target = tab.dataset.taskTab;
                tabs.forEach((item) => item.classList.toggle('active', item === tab));
                panels.forEach((panel) => {
                    const isActive = panel.dataset.taskPanel === target;
                    panel.classList.toggle('active', isActive);
                    panel.hidden = !isActive;
                });
            });
        });
    }

    initTaskTabs();

    function elapsedSince(isoDate) {
        if (!isoDate) {
            return 0;
        }
        const started = new Date(isoDate);
        if (Number.isNaN(started.getTime())) {
            return 0;
        }
        return Math.max(Math.floor((Date.now() - started.getTime()) / 1000), 0);
    }

    function refreshTimerRows() {
        const taskSeconds = state.activeTaskStartedAt ? elapsedSince(state.activeTaskStartedAt) : 0;
        const workSeconds = state.baseWorkSeconds + (state.isWorkRunning && state.activeWorkStartedAt ? elapsedSince(state.activeWorkStartedAt) : 0);
        const pauseSeconds = state.basePauseSeconds + (state.isPauseRunning && state.activePauseStartedAt ? elapsedSince(state.activePauseStartedAt) : 0);

        if (taskTimerNode) {
            taskTimerNode.textContent = formatSeconds(taskSeconds);
        }
        if (workTimerNode) {
            workTimerNode.textContent = formatSeconds(workSeconds);
        }
        if (pauseTimerNode) {
            pauseTimerNode.textContent = formatSeconds(pauseSeconds);
        }
    }

    function updatePauseButtonLabel() {
        if (!pauseButton) {
            return;
        }
        pauseButton.textContent = state.isPauseRunning ? "FIN PAUSE" : "PAUSE";
    }

    function setActiveTaskVisual(label) {
        taskItems.forEach((taskItem) => {
            taskItem.classList.toggle("active", taskItem.dataset.taskLabel === label);
        });
    }

    async function postTimer(url, payload) {
        const csrfToken = config.csrfToken || getCookie("csrftoken");
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": csrfToken,
            },
            body: new URLSearchParams(payload).toString(),
        });
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = {};
        }
        if (!response.ok) {
            const message = data.error || "Impossible de mettre à jour la tâche. Réessayez.";
            throw new Error(message);
        }
        return data;
    }

    function showTaskFeedback(message) {
        window.alert(message);
    }

    async function completeTask(taskItem, switchEl) {
        const taskLabel = taskItem.dataset.taskLabel || "";
        const taskId = taskItem.dataset.taskId || "";
        if (!taskLabel && !taskId) {
            return;
        }
        if (switchEl.classList.contains("active") || taskItem.dataset.taskStatus === "done") {
            return;
        }
        switchEl.classList.add("is-loading");
        try {
            const payload = { task_label: taskLabel };
            if (taskId) {
                payload.task_id = taskId;
            }
            await postTimer(config.completeTaskUrl, payload);
            switchEl.classList.add("active");
            switchEl.setAttribute("aria-checked", "true");
            taskItem.dataset.taskStatus = "done";
            if (state.activeTaskLabel === taskLabel) {
                state.activeTaskLabel = "";
                state.activeTaskStartedAt = "";
            }
            setActiveTaskVisual("");
            moveTaskToDonePanel(taskItem);
            updateTaskProgress();
            revealNextTaskBatch();
        } catch (error) {
            showTaskFeedback(error.message || "Impossible de valider la tâche.");
            console.error(error);
        } finally {
            switchEl.classList.remove("is-loading");
        }
    }

    async function startTask(taskItem) {
        const taskLabel = taskItem.dataset.taskLabel || "";
        const taskId = taskItem.dataset.taskId || "";
        if (!taskLabel && !taskId) {
            return;
        }
        if (taskItem.dataset.taskStatus === "done") {
            return;
        }
        try {
            const payload = { task_label: taskLabel };
            if (taskId) {
                payload.task_id = taskId;
            }
            await postTimer(config.startTaskUrl, payload);
            state.activeTaskLabel = taskLabel;
            state.activeTaskStartedAt = new Date().toISOString();
            taskItem.dataset.taskStatus = "in_progress";
            state.baseTaskSeconds = 0;
            state.isPauseRunning = false;
            state.activePauseStartedAt = "";
            setActiveTaskVisual(taskLabel);
            updatePauseButtonLabel();
        } catch (error) {
            showTaskFeedback(error.message || "Impossible de démarrer la tâche.");
            console.error(error);
        }
    }

    taskItems.forEach((taskItem) => {
        const switchEl = taskItem.querySelector(".toggle-switch");
        if (switchEl) {
            switchEl.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                completeTask(taskItem, switchEl);
            });
            switchEl.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    completeTask(taskItem, switchEl);
                }
            });
        }

        taskItem.addEventListener("click", function (event) {
            if (event.target.closest(".toggle-switch")) {
                return;
            }
            startTask(taskItem);
        });
    });

    if (pauseButton) {
        pauseButton.addEventListener("click", async function () {
            try {
                const result = await postTimer(config.togglePauseUrl, {});
                if (result.is_pause_running) {
                    state.isPauseRunning = true;
                    state.activePauseStartedAt = new Date().toISOString();
                    if (state.activeTaskStartedAt) {
                        state.baseTaskSeconds += elapsedSince(state.activeTaskStartedAt);
                        state.activeTaskStartedAt = "";
                        state.activeTaskLabel = "";
                        setActiveTaskVisual("");
                    }
                } else {
                    state.isPauseRunning = false;
                    state.basePauseSeconds += elapsedSince(state.activePauseStartedAt);
                    state.activePauseStartedAt = "";
                }
                updatePauseButtonLabel();
            } catch (error) {
                console.error(error);
            }
        });
    }

    if (menuToggle && sidebar) {
        menuToggle.addEventListener("click", function () {
            sidebar.classList.toggle("open");
        });
        document.addEventListener("click", function (event) {
            if (!sidebar.contains(event.target) && !menuToggle.contains(event.target)) {
                sidebar.classList.remove("open");
            }
        });
    }

    updatePauseButtonLabel();
    if (state.activeTaskLabel) {
        setActiveTaskVisual(state.activeTaskLabel);
    }
    taskItems.forEach((taskItem) => {
        if (taskItem.dataset.taskStatus === "done") {
            taskItem.querySelector(".toggle-switch")?.classList.add("active");
            taskItem.classList.add("completed");
        }
        if (taskItem.dataset.taskStatus === "in_progress") {
            taskItem.classList.add("active");
        }
    });
    updateTaskProgress();
    updateNotificationBadges();
    refreshTimerRows();
    // Ne pas faire tourner un timer chaque seconde hors Accueil
    if (taskTimerNode || workTimerNode || pauseTimerNode) {
        window.setInterval(refreshTimerRows, 1000);
    }
});
