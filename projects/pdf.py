"""PDF A4 du rapport mensuel des projets."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _p(text):
    return escape(str(text or '—'))


def build_monthly_project_report_pdf(report) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Rapport projets {report['month_label']}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'MonthTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#111827'),
        spaceAfter=2,
    )
    subtitle = ParagraphStyle(
        'MonthSub',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontName='Helvetica',
        fontSize=11,
        textColor=colors.HexColor('#374151'),
        spaceAfter=4,
    )
    note = ParagraphStyle(
        'MonthNote',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=10,
    )
    section = ParagraphStyle(
        'MonthSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#111827'),
        spaceBefore=12,
        spaceAfter=6,
    )
    cell = ParagraphStyle(
        'MonthCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#111827'),
    )
    header_cell = ParagraphStyle(
        'MonthHead',
        parent=cell,
        fontName='Helvetica-Bold',
        textColor=colors.white,
    )

    story = [
        Paragraph('Groupe Agence Mwinda', title),
        Paragraph(f"Rapport mensuel des projets — {_p(report['month_label'])}", subtitle),
        Paragraph(
            'Projets créés ce mois-ci, ou dont la période touche ce mois. Le statut indiqué est le statut actuel.',
            note,
        ),
    ]

    summary = [['Statut', 'Nombre']]
    summary.append(['Total', str(report['total'])])
    for group in report['groups']:
        summary.append([group['label'], str(group['count'])])
    summary_table = Table(summary, colWidths=[120 * mm, 58 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fde047')),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#111827')),
        ('BACKGROUND', (0, 2), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    for group in report['groups']:
        if not group['projects']:
            continue
        story.append(Paragraph(f"{_p(group['label'])} ({group['count']})", section))
        rows = [[
            Paragraph('Projet', header_cell),
            Paragraph('Branche', header_cell),
            Paragraph('Période', header_cell),
        ]]
        for project in group['projects']:
            start = project.start_date.strftime('%d/%m/%Y') if project.start_date else '—'
            end = project.end_date.strftime('%d/%m/%Y') if project.end_date else '—'
            rows.append([
                Paragraph(_p(project.name), cell),
                Paragraph(_p(project.get_branch_display_label()), cell),
                Paragraph(f'{start} → {end}', cell),
            ])
        table = Table(rows, colWidths=[78 * mm, 48 * mm, 52 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(table)

    doc.build(story)
    return buffer.getvalue()
