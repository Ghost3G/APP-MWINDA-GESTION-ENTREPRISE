"""PDF A4 — liste de présence mensuelle par agent (avec diagrammes rythme)."""
from io import BytesIO

from django.utils import timezone
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _build_line_chart(labels, values, ref_value, ref_label, title, line_color, width=170 * mm, height=55 * mm):
    """Courbe simple (heures) avec ligne de référence 8h/17h."""
    drawing = Drawing(width, height)
    left, right, bottom, top = 28, width - 8, 18, height - 14
    plot_w = right - left
    plot_h = top - bottom

    drawing.add(String(left, height - 10, title, fontSize=8, fillColor=colors.HexColor('#111827')))
    drawing.add(Rect(left, bottom, plot_w, plot_h, strokeColor=colors.HexColor('#e5e7eb'), fillColor=colors.white, strokeWidth=0.6))

    y_min, y_max = 7.0, 19.0
    n = max(len(labels), 1)

    def x_at(i):
        if n <= 1:
            return left + plot_w / 2
        return left + (i / (n - 1)) * plot_w

    def y_at(v):
        ratio = (v - y_min) / (y_max - y_min)
        return bottom + max(0, min(1, ratio)) * plot_h

    # Grille / labels Y
    for hour in (8, 10, 12, 14, 17):
        y = y_at(hour)
        drawing.add(Line(left, y, right, y, strokeColor=colors.HexColor('#f3f4f6'), strokeWidth=0.5))
        drawing.add(String(2, y - 3, f'{hour:02d}h', fontSize=6, fillColor=colors.HexColor('#6b7280')))

    # Ligne de référence
    ref_y = y_at(ref_value)
    drawing.add(Line(left, ref_y, right, ref_y, strokeColor=colors.HexColor('#ca8a04'), strokeWidth=1.2, strokeDashArray=[3, 2]))
    drawing.add(String(right - 42, ref_y + 2, ref_label, fontSize=6, fillColor=colors.HexColor('#a16207')))

    points = []
    for i, value in enumerate(values):
        if value is None:
            continue
        points.append((i, value))

    for idx in range(1, len(points)):
        i0, v0 = points[idx - 1]
        i1, v1 = points[idx]
        if i1 == i0 + 1:
            drawing.add(Line(
                x_at(i0), y_at(v0), x_at(i1), y_at(v1),
                strokeColor=line_color, strokeWidth=1.4,
            ))

    for i, value in points:
        drawing.add(Circle(x_at(i), y_at(value), 2.2, fillColor=line_color, strokeColor=line_color))

    # Labels X (échantillon)
    step = max(1, n // 8)
    for i, label in enumerate(labels):
        if i % step == 0 or i == n - 1:
            drawing.add(String(x_at(i) - 8, 4, label, fontSize=5.5, fillColor=colors.HexColor('#6b7280')))

    return drawing


def _build_absence_pie(present, absent, width=70 * mm, height=55 * mm):
    drawing = Drawing(width, height)
    drawing.add(String(8, height - 10, 'Présence / Absence (jours ouvrés)', fontSize=8, fillColor=colors.HexColor('#111827')))
    total = present + absent
    if total <= 0:
        drawing.add(String(18, height / 2, 'Aucune donnée', fontSize=8, fillColor=colors.HexColor('#6b7280')))
        return drawing

    pie = Pie()
    pie.x = 12
    pie.y = 8
    pie.width = 38
    pie.height = 38
    pie.data = [present, absent]
    pie.labels = None
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white
    pie.slices[0].fillColor = colors.HexColor('#16a34a')
    pie.slices[1].fillColor = colors.HexColor('#dc2626')
    drawing.add(pie)
    drawing.add(String(54, 30, f'Présents : {present}', fontSize=7, fillColor=colors.HexColor('#166534')))
    drawing.add(String(54, 18, f'Absents : {absent}', fontSize=7, fillColor=colors.HexColor('#991b1b')))
    return drawing


def build_presence_monthly_pdf(payload) -> bytes:
    agent = payload['agent']
    sessions = payload['sessions']
    period_label = payload['period_label']
    rhythm = payload.get('rhythm_data') or {}
    stats = rhythm.get('stats') or {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f'Présence {agent.get_display_name()} {period_label}',
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'PresTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=15,
        spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        'PresSub',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=10,
    )
    section = ParagraphStyle(
        'PresSec',
        parent=styles['Heading2'],
        fontSize=11,
        spaceBefore=8,
        spaceAfter=4,
    )
    small = ParagraphStyle('PresSmall', parent=styles['Normal'], fontSize=8, leading=11)

    work_start = payload.get('work_start') or rhythm.get('work_start_label') or '08:30'
    work_end = payload.get('work_end') or rhythm.get('work_end_label') or '17:30'
    schedule_summary = payload.get('schedule_summary') or rhythm.get('schedule_summary') or (
        'Lun–Ven 08:30–17:30 · Sam 09:00–13:00'
    )

    story = [
        Paragraph('Agence Mwinda — Liste de présence', title),
        Paragraph(
            f'{agent.get_labeled_name()} (@{agent.username})<br/>'
            f'Mois : {period_label} · {payload["start_day"].strftime("%d/%m/%Y")} → {payload["end_day"].strftime("%d/%m/%Y")}<br/>'
            f'Horaires de service : {schedule_summary}<br/>'
            f'Réf. journée (semaine) : {work_start} – {work_end}',
            subtitle,
        ),
    ]

    summary = [
        ['Jours présents', str(payload['present_days'])],
        ['Nombre de connexions', str(payload['session_count'])],
        ['Temps total connecté', payload['total_duration_label']],
        ['À l’heure / Retards', f"{stats.get('on_time_arrivals', 0)} / {stats.get('late_arrivals', 0)}"],
        ['Départs OK / Parti tôt', f"{stats.get('on_time_departures', 0)} / {stats.get('early_departures', 0)}"],
        ['Absents (jours ouvrés)', str(stats.get('absent_days', 0))],
    ]
    summary_table = Table(summary, colWidths=[70 * mm, 100 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    labels = rhythm.get('labels') or []
    if labels:
        story.append(Paragraph('Diagrammes — rythme de travail', section))
        story.append(_build_line_chart(
            labels,
            rhythm.get('arrival_hours') or [],
            float(rhythm.get('work_start') or 8),
            f'Réf. {work_start}',
            'Heure d’arrivée',
            colors.HexColor('#2563eb'),
        ))
        story.append(Spacer(1, 6))
        story.append(_build_line_chart(
            labels,
            rhythm.get('departure_hours') or [],
            float(rhythm.get('work_end') or 17),
            f'Réf. {work_end}',
            'Heure de départ',
            colors.HexColor('#ea580c'),
        ))
        story.append(Spacer(1, 6))
        absence = rhythm.get('absence_chart') or {}
        values = absence.get('values') or [0, 0]
        present = values[0] if len(values) > 0 else 0
        absent = values[1] if len(values) > 1 else 0
        story.append(_build_absence_pie(present, absent))
        story.append(Spacer(1, 8))

    story.append(Paragraph('Détail des connexions', section))
    data = [['Date', 'Login', 'Déconnexion', 'Durée', 'Statut']]
    for row in sessions:
        local_login = timezone.localtime(row['login_at'])
        local_logout = timezone.localtime(row['logout_at']) if row['logout_at'] else None
        if row.get('arrival_status') == 'late':
            status = 'Retard'
        elif row.get('departure_status') == 'early':
            status = 'Parti tôt'
        elif row['is_online']:
            status = 'En ligne'
        else:
            status = 'OK'
        data.append([
            local_login.strftime('%d/%m/%Y'),
            local_login.strftime('%H:%M'),
            local_logout.strftime('%H:%M') if local_logout else '—',
            row['duration_label'],
            status,
        ])

    if len(data) == 1:
        story.append(Paragraph('Aucune connexion enregistrée ce mois-ci.', small))
    else:
        table = Table(data, colWidths=[28 * mm, 28 * mm, 32 * mm, 28 * mm, 30 * mm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (1, 1), (3, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(table)

    doc.build(story)
    return buffer.getvalue()


def build_overtime_pdf(*, agent, period_label, start, end, summary_row) -> bytes:
    """PDF individuel — fiche heures sup. d'un seul collaborateur."""
    total_days = summary_row['total_days']
    entries = summary_row['entries']
    total_label = str(total_days).replace('.', ',')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f'Heures sup. {agent.get_display_name()} {period_label}',
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'OtTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=15,
        spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        'OtSub',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=12,
    )
    section = ParagraphStyle(
        'OtSec',
        parent=styles['Heading2'],
        fontSize=11,
        spaceBefore=8,
        spaceAfter=4,
    )
    small = ParagraphStyle('OtSmall', parent=styles['Normal'], fontSize=8, leading=11)

    story = [
        Paragraph('Agence Mwinda — Heures supplémentaires', title),
        Paragraph(
            f'{agent.get_labeled_name()} (@{agent.username})<br/>'
            f'{agent.get_title_label()}<br/>'
            f'{period_label}<br/>'
            f'Période : {start.strftime("%d/%m/%Y")} → {end.strftime("%d/%m/%Y")}<br/>'
            f'Horaires de référence : lun–ven 08h30–17h30 · sam 09h00–13h00',
            subtitle,
        ),
    ]

    summary_data = [
        ['Total jours comptabilisés', f'{total_label} jour(s)'],
        ['Nombre de saisies', str(len(entries))],
    ]
    summary_table = Table(summary_data, colWidths=[70 * mm, 100 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    detail_data = [['Date', 'Jours', 'Origine', 'Notes', 'Saisi par']]
    for entry in entries:
        detail_data.append([
            entry.work_date.strftime('%d/%m/%Y'),
            str(entry.days).replace('.', ','),
            entry.get_source_display(),
            Paragraph(entry.notes or '—', small),
            entry.created_by.get_display_name() if entry.created_by_id else '—',
        ])
    if len(detail_data) == 1:
        story.append(Paragraph('Aucune saisie enregistrée sur cette période.', small))
    else:
        story.append(Paragraph('Détail des saisies', section))
        detail_table = Table(detail_data, colWidths=[28 * mm, 18 * mm, 32 * mm, 72 * mm, 38 * mm])
        detail_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(detail_table)

    doc.build(story)
    return buffer.getvalue()
