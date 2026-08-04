/**
 * Sélecteur de date français (JJ/MM/AAAA) pour tous les input[type=date].
 * Conserve la valeur ISO (YYYY-MM-DD) pour les formulaires.
 */
(function () {
    const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
    const MONTHS = [
        'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
    ];

    let openPicker = null;

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function isoToParts(iso) {
        if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
        const [y, m, d] = iso.split('-').map(Number);
        return { y, m, d };
    }

    function partsToIso(y, m, d) {
        return `${y}-${pad(m)}-${pad(d)}`;
    }

    function partsToDisplay(y, m, d) {
        return `${pad(d)}/${pad(m)}/${y}`;
    }

    function displayToIso(text) {
        const cleaned = (text || '').trim().replace(/[.\-]/g, '/');
        const match = cleaned.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
        if (!match) return '';
        const d = Number(match[1]);
        const m = Number(match[2]);
        const y = Number(match[3]);
        const dt = new Date(y, m - 1, d);
        if (dt.getFullYear() !== y || dt.getMonth() !== m - 1 || dt.getDate() !== d) return '';
        return partsToIso(y, m, d);
    }

    function closeOpenPicker() {
        if (!openPicker) return;
        openPicker.classList.remove('is-open');
        openPicker = null;
    }

    function enhanceInput(input) {
        if (!input || input.dataset.frDatepicker === '1') return;
        if (input.type !== 'date') return;

        input.dataset.frDatepicker = '1';
        input.classList.add('fr-dp-native');

        const wrap = document.createElement('div');
        wrap.className = 'fr-dp';

        const display = document.createElement('input');
        display.type = 'text';
        display.className = 'fr-dp-display';
        display.inputMode = 'numeric';
        display.autocomplete = 'off';
        display.placeholder = 'JJ/MM/AAAA';
        display.setAttribute('aria-label', input.getAttribute('aria-label') || 'Date (jour/mois/année)');
        if (input.required) display.required = true;
        if (input.disabled) display.disabled = true;

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'fr-dp-toggle';
        toggle.setAttribute('aria-label', 'Ouvrir le calendrier');
        toggle.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <rect x="3" y="5" width="18" height="16" rx="2"></rect>
                <path d="M3 10h18M8 3v4M16 3v4"></path>
            </svg>`;

        const panel = document.createElement('div');
        panel.className = 'fr-dp-panel';
        panel.hidden = true;

        const parent = input.parentNode;
        parent.insertBefore(wrap, input);
        wrap.appendChild(display);
        wrap.appendChild(toggle);
        wrap.appendChild(panel);
        wrap.appendChild(input);

        let viewYear;
        let viewMonth;

        function syncFromNative() {
            const parts = isoToParts(input.value);
            if (parts) {
                display.value = partsToDisplay(parts.y, parts.m, parts.d);
                viewYear = parts.y;
                viewMonth = parts.m - 1;
            } else {
                display.value = '';
                const now = new Date();
                viewYear = now.getFullYear();
                viewMonth = now.getMonth();
            }
        }

        function renderPanel() {
            const selected = isoToParts(input.value);
            const first = new Date(viewYear, viewMonth, 1);
            const startOffset = (first.getDay() + 6) % 7;
            const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
            const today = new Date();

            let daysHtml = '';
            for (let i = 0; i < startOffset; i += 1) {
                daysHtml += '<span class="fr-dp-day is-empty"></span>';
            }
            for (let day = 1; day <= daysInMonth; day += 1) {
                const iso = partsToIso(viewYear, viewMonth + 1, day);
                const isSelected = selected
                    && selected.y === viewYear
                    && selected.m === viewMonth + 1
                    && selected.d === day;
                const isToday = today.getFullYear() === viewYear
                    && today.getMonth() === viewMonth
                    && today.getDate() === day;
                const cls = ['fr-dp-day'];
                if (isSelected) cls.push('is-selected');
                if (isToday) cls.push('is-today');
                daysHtml += `<button type="button" class="${cls.join(' ')}" data-iso="${iso}">${day}</button>`;
            }

            const yearOptions = [];
            const baseYear = today.getFullYear();
            for (let y = baseYear - 40; y <= baseYear + 10; y += 1) {
                yearOptions.push(`<option value="${y}" ${y === viewYear ? 'selected' : ''}>${y}</option>`);
            }

            panel.innerHTML = `
                <div class="fr-dp-head">
                    <button type="button" class="fr-dp-nav" data-nav="-1" aria-label="Mois précédent">‹</button>
                    <div class="fr-dp-selectors">
                        <select class="fr-dp-month" aria-label="Mois">
                            ${MONTHS.map((name, idx) => `<option value="${idx}" ${idx === viewMonth ? 'selected' : ''}>${name}</option>`).join('')}
                        </select>
                        <select class="fr-dp-year" aria-label="Année">
                            ${yearOptions.join('')}
                        </select>
                    </div>
                    <button type="button" class="fr-dp-nav" data-nav="1" aria-label="Mois suivant">›</button>
                </div>
                <div class="fr-dp-weekdays">
                    ${WEEKDAYS.map((d) => `<span>${d}</span>`).join('')}
                </div>
                <div class="fr-dp-days">${daysHtml}</div>
                <div class="fr-dp-footer">
                    <button type="button" class="fr-dp-today" data-today>Aujourd’hui</button>
                    <button type="button" class="fr-dp-clear" data-clear>Effacer</button>
                </div>`;

            panel.querySelector('[data-nav="-1"]')?.addEventListener('click', () => {
                viewMonth -= 1;
                if (viewMonth < 0) {
                    viewMonth = 11;
                    viewYear -= 1;
                }
                renderPanel();
            });
            panel.querySelector('[data-nav="1"]')?.addEventListener('click', () => {
                viewMonth += 1;
                if (viewMonth > 11) {
                    viewMonth = 0;
                    viewYear += 1;
                }
                renderPanel();
            });
            panel.querySelector('.fr-dp-month')?.addEventListener('change', (event) => {
                viewMonth = Number(event.target.value);
                renderPanel();
            });
            panel.querySelector('.fr-dp-year')?.addEventListener('change', (event) => {
                viewYear = Number(event.target.value);
                renderPanel();
            });
            panel.querySelectorAll('.fr-dp-day[data-iso]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    input.value = btn.dataset.iso;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    syncFromNative();
                    closePanel();
                });
            });
            panel.querySelector('[data-today]')?.addEventListener('click', () => {
                const now = new Date();
                input.value = partsToIso(now.getFullYear(), now.getMonth() + 1, now.getDate());
                input.dispatchEvent(new Event('change', { bubbles: true }));
                syncFromNative();
                closePanel();
            });
            panel.querySelector('[data-clear]')?.addEventListener('click', () => {
                input.value = '';
                input.dispatchEvent(new Event('change', { bubbles: true }));
                syncFromNative();
                closePanel();
            });
        }

        function openPanel() {
            if (input.disabled) return;
            closeOpenPicker();
            syncFromNative();
            renderPanel();
            panel.hidden = false;
            wrap.classList.add('is-open');
            openPicker = wrap;
        }

        function closePanel() {
            panel.hidden = true;
            wrap.classList.remove('is-open');
            if (openPicker === wrap) openPicker = null;
        }

        toggle.addEventListener('click', (event) => {
            event.preventDefault();
            if (wrap.classList.contains('is-open')) closePanel();
            else openPanel();
        });

        display.addEventListener('focus', () => openPanel());

        display.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') closePanel();
            if (event.key === 'Enter') {
                event.preventDefault();
                const iso = displayToIso(display.value);
                if (iso) {
                    input.value = iso;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    syncFromNative();
                    closePanel();
                }
            }
        });

        display.addEventListener('blur', () => {
            const iso = displayToIso(display.value);
            if (iso) {
                input.value = iso;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            syncFromNative();
        });

        input.addEventListener('change', syncFromNative);
        syncFromNative();
    }

    function enhanceAll(root = document) {
        root.querySelectorAll('input[type="date"]').forEach(enhanceInput);
    }

    document.addEventListener('click', (event) => {
        if (!openPicker) return;
        if (openPicker.contains(event.target)) return;
        const panel = openPicker.querySelector('.fr-dp-panel');
        if (panel) panel.hidden = true;
        closeOpenPicker();
    });

    document.addEventListener('DOMContentLoaded', () => {
        enhanceAll();
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof HTMLElement)) return;
                    if (node.matches?.('input[type="date"]')) enhanceInput(node);
                    else enhanceAll(node);
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });

    window.MwindaFrDatepicker = { enhanceAll, enhanceInput };
})();
