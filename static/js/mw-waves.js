(function () {
    'use strict';

    var PALETTE = ['#fde047', '#fb923c', '#2dd4bf', '#38bdf8', '#f87171', '#4ade80', '#a78bfa', '#f472b6'];

    function $(sel, root) { return (root || document).querySelector(sel); }
    function el(name, attrs) {
        var n = document.createElementNS('http://www.w3.org/2000/svg', name);
        Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
        return n;
    }
    function fmt(n) {
        n = Number(n) || 0;
        if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '') + 'k';
        return String(Math.round(n));
    }

    function seriesPoints(value, max, count, seed) {
        var pts = [];
        var base = max > 0 ? value / max : 0;
        for (var i = 0; i < count; i++) {
            var t = i / (count - 1);
            var wobble = Math.sin((t * 6 + seed) * Math.PI) * 0.12
                + Math.sin((t * 13 + seed * 1.7) * Math.PI) * 0.06;
            var v = Math.max(0.04, base * (0.72 + wobble + t * 0.18));
            pts.push(v * max);
        }
        return pts;
    }

    function smoothArea(points, W, H, padL, padR, padT, padB, baseline) {
        var n = points.length;
        var innerW = W - padL - padR;
        var innerH = H - padT - padB;
        var max = Math.max.apply(null, points.concat([1]));
        var coords = points.map(function (v, i) {
            var x = padL + (i / (n - 1)) * innerW;
            var y = padT + innerH - (v / max) * innerH * 0.92;
            return [x, y];
        });
        var d = 'M ' + coords[0][0].toFixed(2) + ' ' + baseline.toFixed(2);
        d += ' L ' + coords[0][0].toFixed(2) + ' ' + coords[0][1].toFixed(2);
        for (var i = 0; i < coords.length - 1; i++) {
            var p0 = coords[i === 0 ? i : i - 1];
            var p1 = coords[i];
            var p2 = coords[i + 1];
            var p3 = coords[i + 2] || p2;
            var cp1x = p1[0] + (p2[0] - p0[0]) / 6;
            var cp1y = p1[1] + (p2[1] - p0[1]) / 6;
            var cp2x = p2[0] - (p3[0] - p1[0]) / 6;
            var cp2y = p2[1] - (p3[1] - p1[1]) / 6;
            d += ' C ' + cp1x.toFixed(2) + ' ' + cp1y.toFixed(2) + ', '
                + cp2x.toFixed(2) + ' ' + cp2y.toFixed(2) + ', '
                + p2[0].toFixed(2) + ' ' + p2[1].toFixed(2);
        }
        d += ' L ' + coords[coords.length - 1][0].toFixed(2) + ' ' + baseline.toFixed(2) + ' Z';
        return { d: d, coords: coords, max: max };
    }

    function smoothStroke(coords) {
        if (!coords.length) return '';
        var d = 'M ' + coords[0][0].toFixed(2) + ' ' + coords[0][1].toFixed(2);
        for (var i = 0; i < coords.length - 1; i++) {
            var p0 = coords[i === 0 ? i : i - 1];
            var p1 = coords[i];
            var p2 = coords[i + 1];
            var p3 = coords[i + 2] || p2;
            var cp1x = p1[0] + (p2[0] - p0[0]) / 6;
            var cp1y = p1[1] + (p2[1] - p0[1]) / 6;
            var cp2x = p2[0] - (p3[0] - p1[0]) / 6;
            var cp2y = p2[1] - (p3[1] - p1[1]) / 6;
            d += ' C ' + cp1x.toFixed(2) + ' ' + cp1y.toFixed(2) + ', '
                + cp2x.toFixed(2) + ' ' + cp2y.toFixed(2) + ', '
                + p2[0].toFixed(2) + ' ' + p2[1].toFixed(2);
        }
        return d;
    }

    function addGlow(defs, id) {
        var f = el('filter', { id: id, x: '-40%', y: '-60%', width: '180%', height: '220%' });
        f.appendChild(el('feGaussianBlur', { stdDeviation: '3.5', result: 'b' }));
        var m = el('feMerge');
        m.appendChild(el('feMergeNode', { in: 'b' }));
        m.appendChild(el('feMergeNode', { in: 'SourceGraphic' }));
        f.appendChild(m);
        defs.appendChild(f);
    }

    function renderAurora(host, series, opts) {
        opts = opts || {};
        var W = 860, H = opts.height || 320;
        var padL = 52, padR = 18, padT = 18, padB = 34;
        var maxVal = Math.max.apply(null, series.map(function (s) { return s.value; }).concat([1]));
        var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
        var defs = el('defs');
        addGlow(defs, 'glow-' + host.id);
        series.forEach(function (s, i) {
            var g = el('linearGradient', { id: 'ag-' + host.id + '-' + i, x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
            g.appendChild(el('stop', { offset: '0%', 'stop-color': s.color, 'stop-opacity': '0.75' }));
            g.appendChild(el('stop', { offset: '100%', 'stop-color': s.color, 'stop-opacity': '0.05' }));
            defs.appendChild(g);
        });
        svg.appendChild(defs);

        var baseline = H - padB;
        var layers = [];
        series.forEach(function (s, i) {
            var pts = seriesPoints(s.value, maxVal, 10, i * 1.7 + 0.4);
            var area = smoothArea(pts, W, H, padL, padR, padT, padB, baseline);
            var g = el('g', { class: 'mw-wave-layer', 'data-i': String(i) });
            g.appendChild(el('path', {
                d: area.d,
                fill: 'url(#ag-' + host.id + '-' + i + ')',
                opacity: String(0.55 + (1 - i / Math.max(series.length, 1)) * 0.25),
            }));
            g.appendChild(el('path', {
                d: smoothStroke(area.coords),
                fill: 'none',
                stroke: s.color,
                'stroke-width': '2.8',
                'stroke-linecap': 'round',
                filter: 'url(#glow-' + host.id + ')',
                opacity: '0.95',
            }));
            svg.appendChild(g);
            layers.push({ g: g, s: s });
        });

        var stage = document.createElement('div');
        stage.className = 'mw-wave-stage';
        stage.style.height = H + 'px';
        stage.appendChild(svg);

        // axes
        var axis = document.createElement('div');
        axis.className = 'mw-wave-axis';
        [0, 0.25, 0.5, 0.75, 1].forEach(function (p) {
            var lab = document.createElement('span');
            lab.className = 'mw-wave-axis__y';
            lab.style.bottom = (p * 100) + '%';
            lab.textContent = fmt(maxVal * p);
            axis.appendChild(lab);
        });
        (opts.xLabels || ['', '', '', '']).forEach(function (label, i, arr) {
            if (!label) return;
            var lab = document.createElement('span');
            lab.className = 'mw-wave-axis__x';
            lab.style.left = ((i / Math.max(arr.length - 1, 1)) * 100) + '%';
            lab.textContent = label;
            axis.appendChild(lab);
        });
        stage.appendChild(axis);

        var tip = document.createElement('div');
        tip.className = 'mw-wave-tip';
        tip.innerHTML = '<strong></strong><span></span>';
        stage.appendChild(tip);

        var legend = document.createElement('div');
        legend.className = 'mw-wave-legend';
        layers.forEach(function (layer, i) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.innerHTML = '<span class="mw-wave-swatch" style="background:' + layer.s.color + ';color:' + layer.s.color + '"></span>'
                + '<span>' + layer.s.label + ' · ' + fmt(layer.s.value) + '</span>';
            btn.addEventListener('mouseenter', function () {
                layers.forEach(function (L, j) {
                    L.g.classList.toggle('is-hot', j === i);
                    L.g.classList.toggle('is-dim', j !== i);
                });
                tip.querySelector('strong').textContent = layer.s.label;
                tip.querySelector('span').textContent = fmt(layer.s.value);
                tip.classList.add('is-on');
                tip.style.left = '56px';
                tip.style.top = '16px';
            });
            btn.addEventListener('mouseleave', function () {
                layers.forEach(function (L) { L.g.classList.remove('is-hot', 'is-dim'); });
                tip.classList.remove('is-on');
            });
            legend.appendChild(btn);
            layer.g.addEventListener('mouseenter', function () { btn.dispatchEvent(new Event('mouseenter')); });
            layer.g.addEventListener('mouseleave', function () { btn.dispatchEvent(new Event('mouseleave')); });
        });

        host.innerHTML = '';
        host.appendChild(stage);
        host.appendChild(legend);
    }

    function renderRibbon(host, item, colors) {
        var W = 640, H = 46;
        var mid = H / 2;
        var amp = 9 + Math.min(12, (item.value || 1) / 10);
        var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
        var defs = el('defs');
        addGlow(defs, 'rg-' + host.id);
        var grad = el('linearGradient', { id: 'rb-' + host.id, x1: '0%', y1: '0%', x2: '100%', y2: '0%' });
        (colors || PALETTE.slice(0, 4)).forEach(function (c, i, arr) {
            grad.appendChild(el('stop', {
                offset: Math.round((i / Math.max(arr.length - 1, 1)) * 100) + '%',
                'stop-color': c,
            }));
        });
        defs.appendChild(grad);
        svg.appendChild(defs);

        var coords = [];
        for (var i = 0; i <= 28; i++) {
            var t = i / 28;
            var y = mid + Math.sin(t * Math.PI * 2.2) * amp + Math.sin(t * Math.PI * 4.1) * (amp * 0.25);
            coords.push([t * W, y]);
        }
        // tube: stroke thick + inner highlight
        svg.appendChild(el('path', {
            d: smoothStroke(coords),
            fill: 'none',
            stroke: 'url(#rb-' + host.id + ')',
            'stroke-width': '14',
            'stroke-linecap': 'round',
            opacity: '0.35',
            filter: 'url(#rg-' + host.id + ')',
        }));
        svg.appendChild(el('path', {
            d: smoothStroke(coords),
            fill: 'none',
            stroke: 'url(#rb-' + host.id + ')',
            'stroke-width': '6',
            'stroke-linecap': 'round',
            opacity: '0.95',
            filter: 'url(#rg-' + host.id + ')',
        }));
        svg.appendChild(el('path', {
            d: smoothStroke(coords),
            fill: 'none',
            stroke: '#ffffff',
            'stroke-width': '1.6',
            'stroke-linecap': 'round',
            opacity: '0.55',
        }));
        host.innerHTML = '';
        host.appendChild(svg);
    }

    function renderStack(host, series) {
        var W = 280, H = 440;
        var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
        var defs = el('defs');
        addGlow(defs, 'sg-' + host.id);
        series.forEach(function (s, i) {
            var g = el('linearGradient', { id: 'st-' + host.id + '-' + i, x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
            g.appendChild(el('stop', { offset: '0%', 'stop-color': '#ffffff', 'stop-opacity': '0.35' }));
            g.appendChild(el('stop', { offset: '18%', 'stop-color': s.color, 'stop-opacity': '0.95' }));
            g.appendChild(el('stop', { offset: '100%', 'stop-color': s.color, 'stop-opacity': '0.12' }));
            defs.appendChild(g);
        });
        svg.appendChild(defs);

        var max = Math.max.apply(null, series.map(function (s) { return s.value; }).concat([1]));
        var band = H / Math.max(series.length, 1);
        series.forEach(function (s, i) {
            var mid = band * i + band * 0.55;
            var amp = 18 + (s.value / max) * 28;
            var coordsTop = [];
            var coordsBot = [];
            for (var x = 0; x <= 24; x++) {
                var t = x / 24;
                var px = t * W;
                var wave = Math.sin(t * Math.PI * 2 + i) * amp + Math.sin(t * Math.PI * 3.4 + i * 1.3) * amp * 0.3;
                coordsTop.push([px, mid + wave - 16]);
                coordsBot.push([px, mid + wave + 16]);
            }
            var d = smoothStroke(coordsTop) + ' ';
            // close with bottom reverse
            for (var j = coordsBot.length - 1; j >= 0; j--) {
                var p = coordsBot[j];
                d += (j === coordsBot.length - 1 ? ' L ' : ' L ') + p[0].toFixed(2) + ' ' + p[1].toFixed(2);
            }
            d += ' Z';
            // rebuild with bezier for top only then line bottom
            d = smoothStroke(coordsTop);
            var rev = coordsBot.slice().reverse();
            d += ' L ' + rev[0][0].toFixed(2) + ' ' + rev[0][1].toFixed(2);
            for (var k = 0; k < rev.length - 1; k++) {
                var a = rev[k], b = rev[k + 1];
                var c1x = a[0] - (a[0] - b[0]) / 3;
                var c2x = a[0] - 2 * (a[0] - b[0]) / 3;
                d += ' C ' + c1x.toFixed(2) + ' ' + a[1].toFixed(2) + ', ' + c2x.toFixed(2) + ' ' + b[1].toFixed(2) + ', ' + b[0].toFixed(2) + ' ' + b[1].toFixed(2);
            }
            d += ' Z';
            var g = el('g', { class: 'mw-wave-layer' });
            g.appendChild(el('path', {
                d: d,
                fill: 'url(#st-' + host.id + '-' + i + ')',
                opacity: '0.9',
                filter: 'url(#sg-' + host.id + ')',
            }));
            g.appendChild(el('path', {
                d: smoothStroke(coordsTop),
                fill: 'none',
                stroke: s.color,
                'stroke-width': '2.4',
                opacity: '0.95',
            }));
            svg.appendChild(g);
        });

        var stage = document.createElement('div');
        stage.className = 'mw-wave-stage';
        stage.appendChild(svg);
        var legend = document.createElement('div');
        legend.className = 'mw-wave-legend';
        series.forEach(function (s) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.innerHTML = '<span class="mw-wave-swatch" style="background:' + s.color + ';color:' + s.color + '"></span><span>' + s.label + ' · ' + fmt(s.value) + '</span>';
            legend.appendChild(btn);
        });
        host.innerHTML = '';
        host.appendChild(stage);
        host.appendChild(legend);
    }

    function seriesFromChart(chart) {
        if (chart.datasets && chart.datasets.length) {
            return chart.datasets.map(function (ds, i) {
                var sum = (ds.values || []).reduce(function (a, b) { return a + (Number(b) || 0); }, 0);
                return { label: ds.label || ('Série ' + (i + 1)), value: sum, color: ds.color || PALETTE[i % PALETTE.length] };
            }).filter(function (s) { return s.value > 0; });
        }
        return (chart.labels || []).map(function (label, i) {
            return {
                label: label,
                value: Number((chart.values || [])[i]) || 0,
                color: (chart.colors && chart.colors[i]) || PALETTE[i % PALETTE.length],
            };
        }).filter(function (s) { return s.value > 0; });
    }

    // Board maquette (Accueil Direction)
    var boardEl = document.getElementById('mw-wave-board-data');
    if (boardEl) {
        try {
            var board = JSON.parse(boardEl.textContent);
            var hero = document.getElementById('mw-wave-hero');
            var stack = document.getElementById('mw-wave-stack');
            if (hero && board.hero && board.hero.length) {
                renderAurora(hero, board.hero, { height: 320, xLabels: board.xLabels || [] });
            }
            if (stack && board.stack && board.stack.length) {
                renderStack(stack, board.stack);
            }
            (board.ribbons || []).forEach(function (rib, i) {
                var host = document.getElementById('mw-wave-ribbon-' + i);
                if (host) renderRibbon(host, rib, rib.colors || PALETTE.slice(i, i + 4));
            });
        } catch (e) { /* ignore */ }
    }

    // Cartes génériques (autres pages)
    var dataEl = document.getElementById('mw-charts-data');
    if (dataEl) {
        var charts;
        try { charts = JSON.parse(dataEl.textContent); } catch (e) { charts = []; }
        if (Array.isArray(charts)) {
            charts.forEach(function (chart) {
                var host = document.getElementById('mw-wave-' + chart.id);
                if (!host) return;
                var series = seriesFromChart(chart);
                if (!series.length) {
                    host.innerHTML = '<div class="mw-wave-empty">Aucune donnée à afficher</div>';
                    return;
                }
                renderAurora(host, series, { height: chart.wide ? 280 : 240 });
            });
        }
    }
})();
