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
    const safeSeconds = Math.max(Math.floor(totalSeconds || 0), 0);
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const seconds = safeSeconds % 60;
    return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function formatHumanDuration(totalSeconds) {
    const safeSeconds = Math.max(Math.floor(totalSeconds || 0), 0);
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const seconds = safeSeconds % 60;
    if (hours) {
        return hours + " h " + String(minutes).padStart(2, "0");
    }
    if (minutes) {
        return minutes + " min";
    }
    return seconds + " s";
}

function formatTimerDisplay(totalSeconds, format) {
    return format === "human" ? formatHumanDuration(totalSeconds) : formatSeconds(totalSeconds);
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
    const openItems = Array.from(document.querySelectorAll('.task-list-panel[data-task-panel="open"] .task-item:not([hidden])'));
    const doneItems = Array.from(document.querySelectorAll('.task-list-panel[data-task-panel="done"] .task-item:not([hidden])'));
    const allOpen = Array.from(document.querySelectorAll('.task-list-panel[data-task-panel="open"] .task-item'));
    const allDone = Array.from(document.querySelectorAll('.task-list-panel[data-task-panel="done"] .task-item'));
    const progressCircle = document.querySelector(".progress-circle");
    const progressValue = document.querySelector(".progress-value");
    const total = allOpen.length + allDone.length;
    const completedCount = allDone.length;

    allOpen.forEach((taskItem) => {
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

    const panelDone = document.querySelector(".task-panel-progress__done");
    const panelTotal = document.querySelector(".task-panel-progress__total");
    const panelFill = document.querySelector(".task-panel-progress__fill");
    const panelTrack = document.querySelector(".task-panel-progress__track");
    if (panelDone) {
        panelDone.textContent = String(completedCount);
    }
    if (panelTotal) {
        panelTotal.textContent = String(total);
    }
    if (panelFill) {
        panelFill.style.width = percent + "%";
    }
    if (panelTrack) {
        panelTrack.setAttribute("aria-valuenow", String(percent));
        panelTrack.setAttribute("aria-valuetext", percent + " pourcent");
    }
}

function wait(ms) {
    return new Promise((resolve) => {
        window.setTimeout(resolve, ms);
    });
}

document.addEventListener("DOMContentLoaded", function () {
    const config = window.dashboardTimerConfig || {};
    const menuToggle = document.querySelector(".menu-toggle");
    const sidebar = document.querySelector(".sidebar-panel");
    const pauseButton = document.querySelector(".pause-button");
    const pauseBanner = document.getElementById("pause-banner");
    const pauseResumeBtn = document.getElementById("pause-resume-btn");
    const pauseBannerTime = document.getElementById("pause-banner-time");
    const taskFocus = document.getElementById("task-focus");
    const taskFocusTitle = document.getElementById("task-focus-title");
    const taskFocusChrono = document.getElementById("task-focus-chrono");
    const taskFocusStop = document.getElementById("task-focus-stop");
    const taskFocusDone = document.getElementById("task-focus-done");
    const taskTimerNode = document.querySelector("#task-timer-row .timer-value");
    const workTimerNode = document.querySelector("#work-timer-row .timer-value");
    const pauseTimerNode = document.querySelector("#pause-timer-row .timer-value");
    const tasksPanel = document.querySelector(".my-tasks-panel");
    let taskItems = Array.from(document.querySelectorAll(".task-item"));
    let pendingComplete = null;

    function toBool(value) {
        return value === true || value === "true";
    }

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

    function closedBaseFromTotal(totalSeconds, startedAtIso, isRunning) {
        const total = Math.max(parseInt(totalSeconds, 10) || 0, 0);
        if (!isRunning || !startedAtIso) {
            return total;
        }
        return Math.max(total - elapsedSince(startedAtIso), 0);
    }

    const state = {
        activeTaskLabel: config.activeTaskLabel || "",
        activeTaskId: "",
        activeTaskStartedAt: config.activeTaskStartedAt || "",
        activePauseStartedAt: config.activePauseStartedAt || "",
        activeWorkStartedAt: config.activeWorkStartedAt || "",
        isPauseRunning: toBool(config.isPauseRunning),
        isWorkRunning: toBool(config.isWorkRunning),
        baseTaskSeconds: closedBaseFromTotal(config.taskSeconds, config.activeTaskStartedAt, Boolean(config.activeTaskStartedAt)),
        baseWorkSeconds: closedBaseFromTotal(config.workSeconds, config.activeWorkStartedAt, toBool(config.isWorkRunning)),
        basePauseSeconds: closedBaseFromTotal(config.pauseSeconds, config.activePauseStartedAt, toBool(config.isPauseRunning)),
    };

    if (state.activeTaskLabel) {
        const activeItem = taskItems.find((item) => item.dataset.taskLabel === state.activeTaskLabel);
        if (activeItem) {
            state.activeTaskId = activeItem.dataset.taskId || "";
        }
    }

    function revealNextTaskBatch() {
        // Conservé pour compatibilité.
    }

    function bumpTabCounts() {
        document.querySelectorAll(".task-tab-count").forEach((badge) => {
            badge.classList.remove("is-bump");
            void badge.offsetWidth;
            badge.classList.add("is-bump");
        });
    }

    function refreshTabCounts() {
        const openTab = document.querySelector('.task-tab[data-task-tab="open"] .task-tab-count');
        const doneTab = document.querySelector('.task-tab[data-task-tab="done"] .task-tab-count');
        if (openTab) {
            openTab.textContent = String(document.querySelectorAll('.task-list-panel[data-task-panel="open"] .task-item').length);
        }
        if (doneTab) {
            doneTab.textContent = String(document.querySelectorAll('.task-list-panel[data-task-panel="done"] .task-item').length);
        }
        bumpTabCounts();
    }

    function moveTaskToDonePanel(taskItem) {
        const donePanel = document.querySelector('.task-list-panel[data-task-panel="done"]');
        if (!donePanel || !taskItem) {
            return;
        }
        const empty = donePanel.querySelector(".task-empty");
        if (empty) {
            empty.remove();
        }
        taskItem.classList.add("completed");
        taskItem.classList.remove("active", "task-new", "next", "is-completing", "is-exiting", "is-started", "is-dimmed");
        taskItem.dataset.taskStatus = "done";
        taskItem.querySelectorAll(".task-new-badge, .task-new-label, .task-new-dot, .task-due-label").forEach((node) => node.remove());
        const actions = taskItem.querySelector(".task-item-actions");
        if (actions) {
            const badge = document.createElement("span");
            badge.className = "task-done-badge";
            badge.setAttribute("aria-label", "Tâche terminée");
            badge.textContent = "Fait";
            actions.replaceWith(badge);
        }
        donePanel.appendChild(taskItem);

        const openPanel = document.querySelector('.task-list-panel[data-task-panel="open"]');
        if (openPanel && !openPanel.querySelector(".task-item") && !openPanel.querySelector(".task-empty")) {
            const p = document.createElement("p");
            p.className = "task-empty";
            p.textContent = "Aucune tâche en cours.";
            openPanel.appendChild(p);
        }
        refreshTabCounts();
    }

    function moveTaskToOpenPanel(taskItem) {
        const openPanel = document.querySelector('.task-list-panel[data-task-panel="open"]');
        if (!openPanel || !taskItem) {
            return;
        }
        const empty = openPanel.querySelector(".task-empty");
        if (empty) {
            empty.remove();
        }
        taskItem.classList.remove("completed", "is-completing", "is-exiting");
        taskItem.dataset.taskStatus = "pending";
        const badge = taskItem.querySelector(".task-done-badge");
        if (badge) {
            const actions = document.createElement("div");
            actions.className = "task-item-actions";
            actions.innerHTML = [
                '<button type="button" class="task-action-btn task-action-btn--start task-start-btn" title="Démarrer le chrono">Démarrer</button>',
                '<button type="button" class="task-action-btn task-action-btn--stop task-stop-btn" title="Arrêter le chrono" hidden>Stop</button>',
                '<button type="button" class="task-action-btn task-action-btn--done task-complete-btn" title="Marquer terminée">Terminer</button>',
            ].join("");
            badge.replaceWith(actions);
            bindTaskItem(taskItem);
        }
        openPanel.prepend(taskItem);
        refreshTabCounts();
    }

    function showTaskToast(type, message, options) {
        const stack = document.querySelector(".task-toast-stack");
        if (!stack) {
            if (type === "error") {
                window.alert(message);
            }
            return null;
        }
        const toast = document.createElement("div");
        toast.className = "task-toast is-" + type;
        const icon = type === "success" ? "✓" : (type === "error" ? "!" : "…");
        toast.innerHTML = '<span class="task-toast__icon" aria-hidden="true">' + icon + '</span><span class="task-toast__text"></span>';
        toast.querySelector(".task-toast__text").textContent = message;

        if (options && options.undoLabel && typeof options.onUndo === "function") {
            const undoBtn = document.createElement("button");
            undoBtn.type = "button";
            undoBtn.className = "task-toast__undo";
            undoBtn.textContent = options.undoLabel;
            undoBtn.addEventListener("click", function (event) {
                event.preventDefault();
                options.onUndo();
                dismissToast(toast);
            });
            toast.appendChild(undoBtn);
        }

        stack.appendChild(toast);
        const lifetime = options && options.durationMs ? options.durationMs : (type === "error" ? 4200 : 2800);
        window.setTimeout(() => {
            if (!toast.isConnected) {
                return;
            }
            toast.style.animation = "taskToastOut 0.28s ease forwards";
            window.setTimeout(() => toast.remove(), 280);
        }, lifetime);
        return toast;
    }

    function dismissToast(toast) {
        if (!toast || !toast.isConnected) {
            return;
        }
        toast.style.animation = "taskToastOut 0.22s ease forwards";
        window.setTimeout(() => toast.remove(), 220);
    }

    function getTaskTitle(taskItem) {
        const titleNode = taskItem.querySelector(".task-item-title");
        if (!titleNode) {
            return "Tâche";
        }
        const clone = titleNode.cloneNode(true);
        clone.querySelectorAll(".task-new-label, .task-due-label").forEach((node) => node.remove());
        return clone.textContent.trim() || "Tâche";
    }

    function initTaskTabs() {
        const tabs = Array.from(document.querySelectorAll(".task-tab"));
        const panels = Array.from(document.querySelectorAll(".task-list-panel"));
        if (!tabs.length) {
            return;
        }
        tabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                const target = tab.dataset.taskTab;
                tabs.forEach((item) => item.classList.toggle("active", item === tab));
                panels.forEach((panel) => {
                    const isActive = panel.dataset.taskPanel === target;
                    panel.classList.toggle("active", isActive);
                    panel.hidden = !isActive;
                });
            });
        });
    }

    function initProjectFilter() {
        const select = document.querySelector("#task_project[data-client-filter]");
        if (!select) {
            return;
        }
        select.addEventListener("change", function () {
            const projectId = select.value;
            document.querySelectorAll(".task-list-panel .task-item").forEach((item) => {
                const match = !projectId || item.dataset.projectId === projectId;
                item.hidden = !match;
            });
            document.querySelectorAll(".task-list-panel").forEach((panel) => {
                const visible = panel.querySelectorAll(".task-item:not([hidden])");
                let empty = panel.querySelector(".task-empty");
                if (!visible.length) {
                    if (!empty) {
                        empty = document.createElement("p");
                        empty.className = "task-empty task-empty--filter";
                        empty.textContent = "Aucune tâche pour ce projet.";
                        panel.appendChild(empty);
                    }
                } else if (empty && empty.classList.contains("task-empty--filter")) {
                    empty.remove();
                }
            });
        });
    }

    function setTimerNode(node, seconds) {
        if (!node) {
            return;
        }
        const format = node.getAttribute("data-format") || "clock";
        node.textContent = formatTimerDisplay(seconds, format);
    }

    function syncFocusCard(taskSeconds) {
        if (!taskFocus) {
            return;
        }
        const show = Boolean(state.activeTaskLabel) && !state.isPauseRunning;
        taskFocus.hidden = !show;
        if (taskFocusTitle) {
            taskFocusTitle.textContent = state.activeTaskLabel || "";
        }
        if (taskFocusChrono) {
            taskFocusChrono.textContent = formatSeconds(taskSeconds);
        }
    }

    function syncPauseUi(pauseSessionSeconds) {
        if (pauseBanner) {
            pauseBanner.hidden = !state.isPauseRunning;
        }
        if (pauseBannerTime) {
            pauseBannerTime.textContent = formatHumanDuration(pauseSessionSeconds || 0);
        }
        if (pauseButton) {
            pauseButton.hidden = state.isPauseRunning;
            pauseButton.textContent = "PAUSE";
        }
        if (tasksPanel) {
            tasksPanel.classList.toggle("is-paused", state.isPauseRunning);
            tasksPanel.dataset.pauseRunning = state.isPauseRunning ? "1" : "0";
        }
    }

    function refreshTimerRows() {
        const taskSeconds = state.activeTaskStartedAt
            ? state.baseTaskSeconds + elapsedSince(state.activeTaskStartedAt)
            : state.baseTaskSeconds;
        const workSeconds = state.baseWorkSeconds + (
            state.isWorkRunning && state.activeWorkStartedAt ? elapsedSince(state.activeWorkStartedAt) : 0
        );
        const pauseSeconds = state.basePauseSeconds + (
            state.isPauseRunning && state.activePauseStartedAt ? elapsedSince(state.activePauseStartedAt) : 0
        );
        const pauseSessionSeconds = state.isPauseRunning && state.activePauseStartedAt
            ? elapsedSince(state.activePauseStartedAt)
            : 0;

        setTimerNode(taskTimerNode, state.activeTaskStartedAt || state.activeTaskLabel ? taskSeconds : 0);
        setTimerNode(workTimerNode, workSeconds);
        setTimerNode(pauseTimerNode, pauseSeconds);
        syncFocusCard(taskSeconds);
        syncPauseUi(pauseSessionSeconds);

        const activeLabel = document.getElementById("active-task-label");
        if (activeLabel) {
            if (state.activeTaskLabel && !state.isPauseRunning) {
                activeLabel.textContent = "En cours : " + state.activeTaskLabel;
                activeLabel.hidden = false;
            } else {
                activeLabel.textContent = "";
                activeLabel.hidden = true;
            }
        }
    }

    function setActiveTaskVisual(label) {
        taskItems = Array.from(document.querySelectorAll(".task-item"));
        const hasActive = Boolean(label) && !state.isPauseRunning;
        taskItems.forEach((taskItem) => {
            const isActive = taskItem.dataset.taskLabel === label && hasActive;
            taskItem.classList.toggle("active", isActive);
            taskItem.classList.toggle("is-dimmed", hasActive && !isActive && taskItem.dataset.taskStatus !== "done");
            const startBtn = taskItem.querySelector(".task-start-btn");
            const stopBtn = taskItem.querySelector(".task-stop-btn");
            if (startBtn) {
                startBtn.hidden = isActive;
            }
            if (stopBtn) {
                stopBtn.hidden = !isActive;
            }
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
            throw new Error(data.error || "Impossible de mettre à jour la tâche. Réessayez.");
        }
        return data;
    }

    function clearActiveTaskLocal(keepBase) {
        if (state.activeTaskStartedAt && keepBase) {
            state.baseTaskSeconds += elapsedSince(state.activeTaskStartedAt);
        } else {
            state.baseTaskSeconds = 0;
        }
        state.activeTaskLabel = "";
        state.activeTaskId = "";
        state.activeTaskStartedAt = "";
        setActiveTaskVisual("");
        refreshTimerRows();
    }

    async function stopTask(taskItem) {
        const taskLabel = (taskItem && taskItem.dataset.taskLabel) || state.activeTaskLabel || "";
        const taskId = (taskItem && taskItem.dataset.taskId) || state.activeTaskId || "";
        if (!taskLabel && !taskId) {
            return;
        }
        try {
            await postTimer(config.stopTaskUrl, {
                task_label: taskLabel,
                task_id: taskId,
            });
            if (taskItem) {
                taskItem.dataset.taskStatus = "pending";
            }
            clearActiveTaskLocal(false);
            showTaskToast("loading", "Chrono arrêté");
        } catch (error) {
            showTaskToast("error", error.message || "Impossible d’arrêter le chrono.");
        }
    }

    async function startTask(taskItem) {
        const taskLabel = taskItem.dataset.taskLabel || "";
        const taskId = taskItem.dataset.taskId || "";
        const taskTitle = getTaskTitle(taskItem);
        if (!taskLabel && !taskId) {
            return;
        }
        if (taskItem.dataset.taskStatus === "done" || taskItem.classList.contains("is-completing")) {
            return;
        }
        try {
            await postTimer(config.startTaskUrl, {
                task_label: taskLabel,
                task_id: taskId,
            });
            state.activeTaskLabel = taskLabel;
            state.activeTaskId = taskId;
            state.activeTaskStartedAt = new Date().toISOString();
            taskItem.dataset.taskStatus = "in_progress";
            state.baseTaskSeconds = 0;
            if (state.isPauseRunning) {
                state.isPauseRunning = false;
                state.basePauseSeconds += elapsedSince(state.activePauseStartedAt);
                state.activePauseStartedAt = "";
            }
            setActiveTaskVisual(taskLabel);
            taskItem.classList.add("is-started");
            window.setTimeout(() => taskItem.classList.remove("is-started"), 900);
            showTaskToast("loading", "Chrono démarré — " + taskTitle);
            refreshTimerRows();
        } catch (error) {
            showTaskToast("error", error.message || "Impossible de démarrer la tâche.");
        }
    }

    async function commitComplete(taskItem) {
        const taskLabel = taskItem.dataset.taskLabel || "";
        const taskId = taskItem.dataset.taskId || "";
        await postTimer(config.completeTaskUrl, {
            task_label: taskLabel,
            task_id: taskId,
        });
        if (state.activeTaskLabel === taskLabel || state.activeTaskId === taskId) {
            clearActiveTaskLocal(false);
        }
    }

    function completeTask(taskItem) {
        const taskTitle = getTaskTitle(taskItem);
        const taskLabel = taskItem.dataset.taskLabel || "";
        const taskId = taskItem.dataset.taskId || "";
        if (taskItem.dataset.taskStatus === "done" || taskItem.classList.contains("is-completing")) {
            return;
        }
        if (pendingComplete && pendingComplete.timerId) {
            window.clearTimeout(pendingComplete.timerId);
            if (pendingComplete.taskItem && pendingComplete.taskItem !== taskItem) {
                moveTaskToOpenPanel(pendingComplete.taskItem);
            }
            pendingComplete = null;
        }

        if (state.activeTaskLabel === taskLabel || (taskId && state.activeTaskId === taskId)) {
            clearActiveTaskLocal(false);
        }

        taskItem.classList.add("is-completing", "is-exiting");
        const openPanel = document.querySelector('.task-list-panel[data-task-panel="open"]');
        if (openPanel) {
            openPanel.classList.add("is-celebrate");
            window.setTimeout(() => openPanel.classList.remove("is-celebrate"), 550);
        }

        window.setTimeout(() => {
            moveTaskToDonePanel(taskItem);
            updateTaskProgress();
            revealNextTaskBatch();
        }, 360);

        const undoToken = { cancelled: false, taskItem };
        const toast = showTaskToast("success", "Terminée : " + taskTitle, {
            durationMs: 5200,
            undoLabel: "Annuler",
            onUndo: function () {
                undoToken.cancelled = true;
                if (pendingComplete && pendingComplete.token === undoToken) {
                    window.clearTimeout(pendingComplete.timerId);
                    pendingComplete = null;
                }
                moveTaskToOpenPanel(taskItem);
                updateTaskProgress();
                showTaskToast("loading", "Annulé — tâche remise en cours");
            },
        });

        const timerId = window.setTimeout(async () => {
            if (undoToken.cancelled) {
                return;
            }
            try {
                await commitComplete(taskItem);
            } catch (error) {
                moveTaskToOpenPanel(taskItem);
                updateTaskProgress();
                showTaskToast("error", error.message || "Impossible de valider la tâche.");
            } finally {
                if (pendingComplete && pendingComplete.token === undoToken) {
                    pendingComplete = null;
                }
                dismissToast(toast);
            }
        }, 5000);

        pendingComplete = { token: undoToken, timerId, taskItem };
    }

    async function togglePause() {
        try {
            const result = await postTimer(config.togglePauseUrl, {});
            if (result.is_pause_running) {
                state.isPauseRunning = true;
                state.activePauseStartedAt = new Date().toISOString();
                if (state.activeTaskStartedAt || state.activeTaskLabel) {
                    clearActiveTaskLocal(true);
                }
            } else {
                state.isPauseRunning = false;
                state.basePauseSeconds += elapsedSince(state.activePauseStartedAt);
                state.activePauseStartedAt = "";
            }
            refreshTimerRows();
        } catch (error) {
            showTaskToast("error", error.message || "Impossible de changer la pause.");
        }
    }

    function bindTaskItem(taskItem) {
        const startBtn = taskItem.querySelector(".task-start-btn");
        const stopBtn = taskItem.querySelector(".task-stop-btn");
        const completeBtn = taskItem.querySelector(".task-complete-btn");

        if (startBtn && !startBtn.dataset.bound) {
            startBtn.dataset.bound = "1";
            startBtn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                startTask(taskItem);
            });
        }
        if (stopBtn && !stopBtn.dataset.bound) {
            stopBtn.dataset.bound = "1";
            stopBtn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                stopTask(taskItem);
            });
        }
        if (completeBtn && !completeBtn.dataset.bound) {
            completeBtn.dataset.bound = "1";
            completeBtn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                completeTask(taskItem);
            });
        }
    }

    initTaskTabs();
    initProjectFilter();

    taskItems.forEach(bindTaskItem);

    if (taskFocusStop) {
        taskFocusStop.addEventListener("click", function () {
            const activeItem = taskItems.find((item) => item.dataset.taskLabel === state.activeTaskLabel);
            stopTask(activeItem || null);
        });
    }
    if (taskFocusDone) {
        taskFocusDone.addEventListener("click", function () {
            const activeItem = taskItems.find((item) => item.dataset.taskLabel === state.activeTaskLabel);
            if (activeItem) {
                completeTask(activeItem);
            }
        });
    }
    if (pauseButton) {
        pauseButton.addEventListener("click", function (event) {
            event.preventDefault();
            togglePause();
        });
    }
    if (pauseResumeBtn) {
        pauseResumeBtn.addEventListener("click", function (event) {
            event.preventDefault();
            togglePause();
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

    if (state.activeTaskLabel) {
        setActiveTaskVisual(state.activeTaskLabel);
    }
    updateTaskProgress();
    updateNotificationBadges();
    refreshTimerRows();
    if (taskTimerNode || workTimerNode || pauseTimerNode || taskFocus) {
        window.setInterval(refreshTimerRows, 1000);
    }
});
