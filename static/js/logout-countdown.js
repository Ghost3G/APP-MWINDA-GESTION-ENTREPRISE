(() => {
    const banner = document.getElementById('logoutCountdownBanner');
    if (!banner || banner.dataset.enabled !== '1') return;

    const valueEl = document.getElementById('logoutCountdownValue');
    const logoutAt = Date.parse(banner.dataset.logoutAt || '');
    const warnAt = Date.parse(banner.dataset.warnAt || '');
    const serverNow = Date.parse(banner.dataset.serverNow || '');
    if (!Number.isFinite(logoutAt) || !Number.isFinite(warnAt) || !Number.isFinite(serverNow)) {
        return;
    }

    const clientOrigin = Date.now();
    const skew = serverNow - clientOrigin;

    function formatRemaining(totalSeconds) {
        const safe = Math.max(0, Math.floor(totalSeconds));
        const minutes = Math.floor(safe / 60);
        const seconds = safe % 60;
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    function tick() {
        const now = Date.now() + skew;
        const remainingMs = logoutAt - now;
        const remainingSec = Math.ceil(remainingMs / 1000);

        if (now < warnAt) {
            banner.hidden = true;
            return;
        }

        if (remainingSec <= 0) {
            banner.hidden = false;
            if (valueEl) valueEl.textContent = '00:00';
            // Laisse le middleware serveur finaliser la déconnexion.
            window.location.reload();
            return;
        }

        banner.hidden = false;
        if (valueEl) valueEl.textContent = formatRemaining(remainingSec);
    }

    tick();
    setInterval(tick, 1000);
})();
