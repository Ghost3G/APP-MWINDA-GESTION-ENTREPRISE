(function () {
    'use strict';

    if (typeof Chart === 'undefined') return;

    var dataEl = document.getElementById('mw-charts-data');
    if (!dataEl) return;

    var charts;
    try {
        charts = JSON.parse(dataEl.textContent);
    } catch (err) {
        return;
    }
    if (!Array.isArray(charts) || !charts.length) return;

    Chart.defaults.color = '#a1a1aa';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.06)';
    Chart.defaults.font.family = '"Plus Jakarta Sans", sans-serif';

    function tooltipBase() {
        return {
            backgroundColor: 'rgba(20, 20, 22, 0.95)',
            borderColor: 'rgba(253, 224, 71, 0.25)',
            borderWidth: 1,
            titleColor: '#f4f4f5',
            bodyColor: '#d4d4d8',
            padding: 12,
            cornerRadius: 10,
        };
    }

    function barGradient(ctx, top, bottom) {
        var gradient = ctx.createLinearGradient(0, 0, 0, 280);
        gradient.addColorStop(0, top);
        gradient.addColorStop(1, bottom);
        return gradient;
    }

    function formatValue(value, chart) {
        if (chart.value_suffix === '$') {
            return Number(value).toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + ' $';
        }
        return Number(value).toLocaleString('fr-FR');
    }

    charts.forEach(function (chart) {
        var canvas = document.getElementById(chart.id);
        if (!canvas) return;

        var ctx = canvas.getContext('2d');
        var height = chart.height || 260;
        canvas.parentElement.style.height = height + 'px';

        if (chart.type === 'doughnut') {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chart.labels,
                    datasets: [{
                        data: chart.values,
                        backgroundColor: chart.colors,
                        borderWidth: 0,
                        hoverOffset: 6,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '62%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { boxWidth: 12, padding: 14, color: '#d4d4d8' },
                        },
                        tooltip: Object.assign({}, tooltipBase(), {
                            callbacks: {
                                label: function (item) {
                                    return ' ' + item.label + ' : ' + formatValue(item.parsed, chart);
                                },
                            },
                        }),
                    },
                },
            });
            return;
        }

        if (chart.type === 'line') {
        var lineColor = (chart.colors && chart.colors[0]) || '#fde047';
        var fillColor = lineColor === '#4ade80' ? 'rgba(74, 222, 128, 0.14)' : 'rgba(253, 224, 71, 0.14)';
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: chart.labels,
                datasets: [{
                    label: chart.dataset_label || 'Valeur',
                    data: chart.values,
                    borderColor: lineColor,
                    backgroundColor: fillColor,
                        pointBackgroundColor: lineColor,
                        pointBorderColor: '#18181b',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2.5,
                        tension: 0.35,
                        fill: true,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: Object.assign({}, tooltipBase(), {
                            callbacks: {
                                label: function (item) {
                                    return ' ' + (chart.dataset_label || 'Valeur') + ' : ' + formatValue(item.parsed.y, chart);
                                },
                            },
                        }),
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: '#d4d4d8', font: { weight: '600', size: 11 } },
                            border: { display: false },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255, 255, 255, 0.06)' },
                            ticks: { color: '#71717a', padding: 8 },
                            border: { display: false },
                        },
                    },
                },
            });
            return;
        }

        if (chart.type === 'bar_grouped') {
            var datasets = (chart.datasets || []).map(function (ds) {
                var color = ds.color || '#fde047';
                return {
                    label: ds.label,
                    data: ds.values,
                    backgroundColor: color,
                    borderColor: color,
                    borderWidth: 1,
                    borderRadius: 8,
                    borderSkipped: false,
                    maxBarThickness: 36,
                };
            });
            new Chart(ctx, {
                type: 'bar',
                data: { labels: chart.labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            align: 'end',
                            labels: { boxWidth: 12, padding: 16, color: '#d4d4d8' },
                        },
                        tooltip: Object.assign({}, tooltipBase(), {
                            callbacks: {
                                label: function (item) {
                                    return ' ' + item.dataset.label + ' : ' + formatValue(item.parsed.y, chart) + (chart.value_suffix === '$' ? '' : '');
                                },
                            },
                        }),
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: '#d4d4d8', font: { weight: '600', size: 11 } },
                            border: { display: false },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255, 255, 255, 0.06)' },
                            ticks: {
                                color: '#71717a',
                                callback: function (v) {
                                    return chart.value_suffix === '$' ? v + ' $' : v;
                                },
                            },
                            border: { display: false },
                        },
                    },
                },
            });
            return;
        }

        var isHorizontal = chart.type === 'bar_horizontal';
        var barType = isHorizontal ? 'bar' : 'bar';
        var colors = chart.colors || [];
        var bgColors = chart.values.map(function (_, i) {
            var c = colors[i] || '#fde047';
            if (c.indexOf('rgba') === 0) return c;
            return c;
        });

        if (!isHorizontal && chart.id.indexOf('reste') === -1 && chart.id.indexOf('overtime') === -1) {
            bgColors = chart.values.map(function (_, i) {
                var base = colors[i] || '#fde047';
                if (base === '#fde047') {
                    return barGradient(ctx, 'rgba(253, 224, 71, 0.95)', 'rgba(202, 138, 4, 0.45)');
                }
                if (base === '#60a5fa') {
                    return barGradient(ctx, 'rgba(96, 165, 250, 0.95)', 'rgba(37, 99, 235, 0.45)');
                }
                if (base === '#4ade80') {
                    return barGradient(ctx, 'rgba(74, 222, 128, 0.95)', 'rgba(22, 163, 74, 0.45)');
                }
                return base;
            });
        }

        new Chart(ctx, {
            type: barType,
            data: {
                labels: chart.labels,
                datasets: [{
                    label: chart.title,
                    data: chart.values,
                    backgroundColor: bgColors,
                    borderColor: colors.map ? colors : bgColors,
                    borderWidth: 1,
                    borderRadius: isHorizontal ? 6 : 10,
                    borderSkipped: false,
                    maxBarThickness: isHorizontal ? 28 : 42,
                }],
            },
            options: {
                indexAxis: isHorizontal ? 'y' : 'x',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: Object.assign({}, tooltipBase(), {
                        callbacks: {
                            label: function (item) {
                                var val = isHorizontal ? item.parsed.x : item.parsed.y;
                                return ' ' + formatValue(val, chart);
                            },
                        },
                    }),
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: isHorizontal ? { color: 'rgba(255, 255, 255, 0.06)' } : { display: false },
                        ticks: {
                            color: isHorizontal ? '#71717a' : '#d4d4d8',
                            font: { weight: isHorizontal ? '400' : '600', size: isHorizontal ? 11 : 12 },
                            callback: isHorizontal
                                ? function (v) {
                                      return chart.value_suffix === '$' ? v + ' $' : v;
                                  }
                                : undefined,
                        },
                        border: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        grid: isHorizontal ? { display: false } : { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: {
                            color: isHorizontal ? '#d4d4d8' : '#71717a',
                            padding: 8,
                            callback: !isHorizontal
                                ? function (v) {
                                      return chart.value_suffix === '$' ? v + ' $' : v;
                                  }
                                : undefined,
                        },
                        border: { display: false },
                    },
                },
            },
        });
    });
})();
