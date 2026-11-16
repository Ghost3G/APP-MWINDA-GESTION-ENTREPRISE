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
            borderColor: 'rgba(253, 224, 71, 0.28)',
            borderWidth: 1,
            titleColor: '#f4f4f5',
            bodyColor: '#d4d4d8',
            padding: 12,
            cornerRadius: 10,
            displayColors: true,
            boxPadding: 4,
        };
    }

    function hexToRgba(hex, alpha) {
        if (!hex || hex.indexOf('rgba') === 0) return hex;
        var h = String(hex).replace('#', '');
        if (h.length === 3) {
            h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
        }
        var r = parseInt(h.slice(0, 2), 16);
        var g = parseInt(h.slice(2, 4), 16);
        var b = parseInt(h.slice(4, 6), 16);
        if (isNaN(r) || isNaN(g) || isNaN(b)) return 'rgba(253, 224, 71,' + alpha + ')';
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function areaGradient(ctx, color, height) {
        var gradient = ctx.createLinearGradient(0, 0, 0, height || 280);
        gradient.addColorStop(0, hexToRgba(color, 0.32));
        gradient.addColorStop(0.55, hexToRgba(color, 0.1));
        gradient.addColorStop(1, hexToRgba(color, 0.02));
        return gradient;
    }

    function horizontalBarFill(color, index, total) {
        if (total <= 1) return hexToRgba(color || '#fde047', 0.88);
        var t = index / Math.max(total - 1, 1);
        var alpha = 0.92 - t * 0.42;
        return hexToRgba(color || '#fde047', Math.max(alpha, 0.38));
    }

    function formatValue(value, chart) {
        if (chart.value_suffix === '$') {
            return Number(value).toLocaleString('fr-FR', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
            }) + ' $';
        }
        return Number(value).toLocaleString('fr-FR');
    }

    function formatCompact(value, chart) {
        var n = Number(value);
        if (chart.value_suffix === '$') {
            if (Math.abs(n) >= 1000) {
                return (n / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 1 }) + 'k $';
            }
            return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' $';
        }
        return n.toLocaleString('fr-FR');
    }

    var centerTotalPlugin = {
        id: 'mwCenterTotal',
        afterDraw: function (chartInstance) {
            if (chartInstance.config.type !== 'doughnut') return;
            var meta = chartInstance.getDatasetMeta(0);
            if (!meta || !meta.data || !meta.data.length) return;
            var chartCfg = chartInstance.config._mwChart || {};
            var values = chartInstance.data.datasets[0].data || [];
            var total = values.reduce(function (sum, v) {
                return sum + Number(v || 0);
            }, 0);
            var ctx = chartInstance.ctx;
            var center = meta.data[0];
            var x = center.x;
            var y = center.y;
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#f4f4f5';
            ctx.font = '700 1.35rem "Plus Jakarta Sans", sans-serif';
            ctx.fillText(formatCompact(total, chartCfg), x, y - 6);
            ctx.fillStyle = '#71717a';
            ctx.font = '500 0.72rem "Plus Jakarta Sans", sans-serif';
            ctx.fillText(chartCfg.center_label || 'Total', x, y + 16);
            ctx.restore();
        },
    };

    function scaleSoft() {
        return {
            x: {
                beginAtZero: true,
                grid: { color: 'rgba(255, 255, 255, 0.045)', drawBorder: false },
                ticks: { color: '#71717a', padding: 8, font: { size: 11 } },
                border: { display: false },
            },
            y: {
                beginAtZero: true,
                grid: { color: 'rgba(255, 255, 255, 0.045)', drawBorder: false },
                ticks: { color: '#71717a', padding: 8, font: { size: 11 } },
                border: { display: false },
            },
        };
    }

    charts.forEach(function (chart) {
        var canvas = document.getElementById(chart.id);
        if (!canvas) return;

        var ctx = canvas.getContext('2d');
        var height = chart.height || 260;
        canvas.parentElement.style.height = height + 'px';

        if (chart.type === 'doughnut') {
            var doughnutChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chart.labels,
                    datasets: [{
                        data: chart.values,
                        backgroundColor: chart.colors,
                        borderColor: '#0f0f12',
                        borderWidth: 3,
                        hoverOffset: 8,
                        hoverBorderColor: 'rgba(253, 224, 71, 0.55)',
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '74%',
                    layout: { padding: 6 },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                padding: 14,
                                color: '#d4d4d8',
                                usePointStyle: true,
                                pointStyle: 'circle',
                            },
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
                plugins: [centerTotalPlugin],
            });
            doughnutChart.config._mwChart = chart;
            return;
        }

        if (chart.type === 'line' || chart.type === 'line_multi') {
            var lineSets;
            if (chart.type === 'line_multi' && chart.datasets) {
                lineSets = chart.datasets.map(function (ds) {
                    var color = ds.color || '#fde047';
                    return {
                        label: ds.label,
                        data: ds.values,
                        borderColor: color,
                        backgroundColor: areaGradient(ctx, color, height),
                        pointBackgroundColor: color,
                        pointBorderColor: '#18181b',
                        pointBorderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        borderWidth: 2.4,
                        tension: 0.42,
                        fill: true,
                    };
                });
            } else {
                var lineColor = (chart.colors && chart.colors[0]) || '#fde047';
                lineSets = [{
                    label: chart.dataset_label || 'Valeur',
                    data: chart.values,
                    borderColor: lineColor,
                    backgroundColor: areaGradient(ctx, lineColor, height),
                    pointBackgroundColor: lineColor,
                    pointBorderColor: '#18181b',
                    pointBorderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    borderWidth: 2.6,
                    tension: 0.42,
                    fill: true,
                }];
            }

            var scales = scaleSoft();
            scales.x.grid.display = false;
            scales.x.ticks.color = '#d4d4d8';
            scales.x.ticks.font = { weight: '600', size: 11 };
            scales.y.ticks.callback = function (v) {
                return chart.value_suffix === '$' ? v + ' $' : v;
            };

            new Chart(ctx, {
                type: 'line',
                data: { labels: chart.labels, datasets: lineSets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            display: lineSets.length > 1,
                            position: 'top',
                            align: 'end',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                padding: 14,
                                color: '#d4d4d8',
                                usePointStyle: true,
                                pointStyle: 'circle',
                            },
                        },
                        tooltip: Object.assign({}, tooltipBase(), {
                            callbacks: {
                                label: function (item) {
                                    return ' ' + item.dataset.label + ' : ' + formatValue(item.parsed.y, chart);
                                },
                            },
                        }),
                    },
                    scales: scales,
                },
            });
            return;
        }

        if (chart.type === 'bar_grouped') {
            var colorSets = (chart.datasets || []).map(function (ds) {
                var color = ds.color || '#fde047';
                return {
                    label: ds.label,
                    data: ds.values,
                    borderColor: color,
                    backgroundColor: areaGradient(ctx, color, height),
                    pointBackgroundColor: color,
                    pointBorderColor: '#18181b',
                    pointBorderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    borderWidth: 2.4,
                    tension: 0.42,
                    fill: true,
                };
            });
            var gScales = scaleSoft();
            gScales.x.grid.display = false;
            gScales.x.ticks.color = '#d4d4d8';
            gScales.x.ticks.font = { weight: '600', size: 11 };
            gScales.y.ticks.callback = function (v) {
                return chart.value_suffix === '$' ? v + ' $' : v;
            };
            new Chart(ctx, {
                type: 'line',
                data: { labels: chart.labels, datasets: colorSets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            align: 'end',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                padding: 14,
                                color: '#d4d4d8',
                                usePointStyle: true,
                                pointStyle: 'circle',
                            },
                        },
                        tooltip: Object.assign({}, tooltipBase(), {
                            callbacks: {
                                label: function (item) {
                                    return ' ' + item.dataset.label + ' : ' + formatValue(item.parsed.y, chart);
                                },
                            },
                        }),
                    },
                    scales: gScales,
                },
            });
            return;
        }

        // Default: horizontal ranking bars (option C)
        var isHorizontal = chart.type !== 'bar_vertical';
        var colors = chart.colors || [];
        var bgColors = chart.values.map(function (_, i) {
            return horizontalBarFill(colors[i] || '#fde047', i, chart.values.length);
        });

        var barScales = scaleSoft();
        if (isHorizontal) {
            barScales.y.grid.display = false;
            barScales.y.ticks.color = '#d4d4d8';
            barScales.y.ticks.font = { weight: '600', size: 11 };
            barScales.x.ticks.callback = function (v) {
                return chart.value_suffix === '$' ? v + ' $' : v;
            };
        } else {
            barScales.x.grid.display = false;
            barScales.x.ticks.color = '#d4d4d8';
            barScales.x.ticks.font = { weight: '600', size: 11 };
            barScales.y.ticks.callback = function (v) {
                return chart.value_suffix === '$' ? v + ' $' : v;
            };
        }

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chart.labels,
                datasets: [{
                    label: chart.title,
                    data: chart.values,
                    backgroundColor: bgColors,
                    borderColor: 'rgba(0,0,0,0)',
                    borderWidth: 0,
                    borderRadius: 8,
                    borderSkipped: false,
                    maxBarThickness: isHorizontal ? 22 : 36,
                    categoryPercentage: 0.72,
                    barPercentage: 0.88,
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
                scales: barScales,
            },
        });
    });
})();
