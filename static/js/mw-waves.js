(function () {
    'use strict';

    var dataEl = document.getElementById('mw-charts-data');
    if (!dataEl) return;

    var charts;
    try {
        charts = JSON.parse(dataEl.textContent);
    } catch (err) {
        return;
    }
    if (!Array.isArray(charts) || !charts.length) return;

    var PALETTE = ['#fde047', '#60a5fa', '#4ade80', '#f87171', '#fb923c', '#a78bfa', '#2dd4bf', '#f472b6'];

    function formatValue(value, chart) {
        var n = Number(value) || 0;
        if (chart && chart.value_suffix === '$') {
            return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' $';
        }
        return n.toLocaleString('fr-FR');
    }

    function seriesFromChart(chart) {
        var items = [];
        if (chart.datasets && chart.datasets.length) {
            chart.datasets.forEach(function (ds, i) {
                var sum = (ds.values || []).reduce(function (a, b) { return a + (Number(b) || 0); }, 0);
                items.push({
                    label: ds.label || ('Série ' + (i + 1)),
                    value: sum,
                    color: ds.color || PALETTE[i % PALETTE.length],
                    values: ds.values || [],
                });
            });
            return items;
        }
        var labels = chart.labels || [];
        var values = chart.values || [];
        var colors = chart.colors || [];
        labels.forEach(function (label, i) {
            items.push({
                label: label,
                value: Number(values[i]) || 0,
                color: colors[i] || PALETTE[i % PALETTE.length],
                values: [Number(values[i]) || 0],
            });
        });
        return items;
    }

    function wavePath(width, height, amp, phase, baseline) {
        var steps = 28;
        var d = 'M 0 ' + height + ' L 0 ' + baseline;
        for (var i = 0; i <= steps; i++) {
            var x = (i / steps) * width;
            var y = baseline - Math.sin((i / steps) * Math.PI * 2 + phase) * amp
                - Math.sin((i / steps) * Math.PI * 3.2 + phase * 1.3) * (amp * 0.28);
            d += ' L ' + x.toFixed(2) + ' ' + y.toFixed(2);
        }
        d += ' L ' + width + ' ' + height + ' Z';
        return d;
    }

    function mountCard(chart) {
        var host = document.getElementById('mw-wave-' + chart.id);
        if (!host) return;

        var items = seriesFromChart(chart).filter(function (it) { return it.value > 0 || (it.values && it.values.some(function (v) { return v > 0; })); });
        if (!items.length) {
            host.innerHTML = '<div class="mw-wave-empty">Aucune donnée à afficher</div>';
            return;
        }

        var max = Math.max.apply(null, items.map(function (it) { return it.value; })) || 1;
        var total = items.reduce(function (a, b) { return a + b.value; }, 0) || 1;
        var W = 640;
        var H = chart.wide ? 260 : 220;

        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
        svg.setAttribute('preserveAspectRatio', 'none');
        svg.setAttribute('aria-hidden', 'true');

        var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        items.forEach(function (it, i) {
            var gid = 'wg-' + chart.id + '-' + i;
            var grad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
            grad.setAttribute('id', gid);
            grad.setAttribute('x1', '0%');
            grad.setAttribute('y1', '0%');
            grad.setAttribute('x2', '100%');
            grad.setAttribute('y2', '100%');
            var s1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            s1.setAttribute('offset', '0%');
            s1.setAttribute('stop-color', it.color);
            s1.setAttribute('stop-opacity', '0.95');
            var s2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            s2.setAttribute('offset', '100%');
            s2.setAttribute('stop-color', it.color);
            s2.setAttribute('stop-opacity', '0.15');
            grad.appendChild(s1);
            grad.appendChild(s2);
            defs.appendChild(grad);
            it._gid = gid;
        });
        svg.appendChild(defs);

        var layers = [];
        items.forEach(function (it, i) {
            var amp = 18 + (it.value / max) * (H * 0.34);
            var baseline = H * 0.72 - i * (H * 0.07);
            var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', wavePath(W, H, amp, i * 0.9, baseline));
            path.setAttribute('fill', 'url(#' + it._gid + ')');
            path.setAttribute('class', 'mw-wave-layer');
            path.dataset.index = String(i);
            path.style.filter = 'drop-shadow(0 0 12px ' + it.color + '66)';
            svg.appendChild(path);
            layers.push(path);
        });

        var stage = document.createElement('div');
        stage.className = 'mw-wave-stage';
        stage.appendChild(svg);

        var tip = document.createElement('div');
        tip.className = 'mw-wave-tip';
        tip.innerHTML = '<strong></strong><span></span>';
        stage.appendChild(tip);

        var legend = document.createElement('div');
        legend.className = 'mw-wave-legend';

        function setActive(index) {
            layers.forEach(function (layer, i) {
                layer.classList.toggle('is-hot', i === index);
                layer.classList.toggle('is-dim', index !== null && i !== index);
            });
            Array.prototype.forEach.call(legend.querySelectorAll('button'), function (btn, i) {
                btn.classList.toggle('is-active', i === index);
            });
        }

        items.forEach(function (it, i) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.innerHTML = '<span class="mw-wave-swatch" style="background:' + it.color + ';color:' + it.color + '"></span>'
                + '<span>' + it.label + ' · ' + formatValue(it.value, chart) + '</span>';
            btn.addEventListener('mouseenter', function () {
                setActive(i);
                tip.querySelector('strong').textContent = it.label;
                tip.querySelector('span').textContent = formatValue(it.value, chart)
                    + (total ? ' · ' + Math.round((it.value / total) * 100) + '%' : '');
                tip.classList.add('is-on');
                tip.style.left = '16px';
                tip.style.top = '16px';
            });
            btn.addEventListener('mouseleave', function () {
                setActive(null);
                tip.classList.remove('is-on');
            });
            btn.addEventListener('click', function () {
                setActive(i);
            });
            legend.appendChild(btn);

            layers[i].addEventListener('mousemove', function (ev) {
                setActive(i);
                var rect = stage.getBoundingClientRect();
                tip.querySelector('strong').textContent = it.label;
                tip.querySelector('span').textContent = formatValue(it.value, chart)
                    + (total ? ' · ' + Math.round((it.value / total) * 100) + '%' : '');
                tip.classList.add('is-on');
                tip.style.left = Math.min(rect.width - 140, Math.max(8, ev.clientX - rect.left + 12)) + 'px';
                tip.style.top = Math.min(rect.height - 60, Math.max(8, ev.clientY - rect.top - 10)) + 'px';
            });
            layers[i].addEventListener('mouseleave', function () {
                setActive(null);
                tip.classList.remove('is-on');
            });
        });

        host.innerHTML = '';
        host.appendChild(stage);
        host.appendChild(legend);
    }

    charts.forEach(mountCard);
})();
