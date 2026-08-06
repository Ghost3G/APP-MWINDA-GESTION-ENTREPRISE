"""Génération PDF A4 des rapports journaliers."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _yes(value):
    return 'Oui' if value else '—'


def build_report_pdf(report) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f'Rapport {report.date}',
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'TitleMw',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=16,
        spaceAfter=8,
    )
    subtitle = ParagraphStyle(
        'SubMw',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=14,
    )
    section = ParagraphStyle(
        'SecMw',
        parent=styles['Heading2'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor('#111827'),
    )
    body = ParagraphStyle(
        'BodyMw',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        alignment=TA_LEFT,
    )

    story = [
        Paragraph('Agence Mwinda — Rapport journalier', title),
        Paragraph(f'{report.project} · {report.date.strftime("%d/%m/%Y")}', subtitle),
    ]

    meta = [
        ['Agent', report.user.get_labeled_name()],
        ['Département', report.get_department_display() if report.department else '—'],
        ['Équipe', report.team_agent or '—'],
        ['Créé le', report.created_at.strftime('%d/%m/%Y %H:%M') if report.created_at else '—'],
    ]
    meta_table = Table(meta, colWidths=[35 * mm, 135 * mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    sections = [
        ('1. Conception', [
            ('Brief reçu', report.conception_brief_received),
            ('Croquis validé', report.conception_croquis_validated),
            ('Modélisation', report.conception_modeling_done),
            ('Fichier prêt', report.conception_file_ready),
        ]),
        ('2. Découpe', [
            ('Bois', report.decoupe_bois_decoupe),
            ('Métal', report.decoupe_metal_decoupe),
            ('PVC', report.decoupe_pvc_decoupe),
            ('Dimensions vérifiées', report.decoupe_dimensions_verified),
        ]),
        ('3. Assemblage', [
            ('Méthode', report.get_assemblage_method_display() or '—'),
            ('Partiel', report.assemblage_partial),
            ('Complet', report.assemblage_complete),
            ('Renforts', report.assemblage_renforts),
        ]),
        ('4. Installation LED', [
            ('Bande posée', report.led_bande_posee),
            ('Alimentation', report.led_alimentation_installee),
            ('Test allumage', report.led_test_allumage),
            ('Câblage sécurisé', report.led_cablage_secure),
        ]),
        ('5. Contrôle qualité', [
            ('Alignement', report.qualite_alignement),
            ('Solidité', report.qualite_solidite),
            ('Finitions', report.qualite_finitions),
            ('Conformité', report.qualite_conformite),
            ('Validation', report.qualite_validation),
        ]),
        ('6. Peinture & finition', [
            ('Ponçage', report.peinture_poncage),
            ('Sous-couche', report.peinture_sous_couche),
            ('Peinture', report.peinture_peinture),
            ('Vernis', report.peinture_vernis),
            ('Nettoyage', report.peinture_nettoyage),
        ]),
        ('7. Livraison / installation', [
            ('Emballage', report.livraison_emballage),
            ('Transport', report.livraison_transport),
            ('Installation', report.livraison_installation),
            ('Rapport photo', report.livraison_rapport_photo),
            ('Projet clôturé', report.livraison_projet_cloture),
        ]),
    ]

    for title_text, rows in sections:
        story.append(Paragraph(title_text, section))
        data = []
        for label, value in rows:
            cell = value if isinstance(value, str) else _yes(value)
            data.append([label, cell])
        table = Table(data, colWidths=[70 * mm, 100 * mm])
        table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

    if report.observations or report.work_done or report.problems or report.objectives:
        story.append(Paragraph('Observations', section))
        if report.observations:
            story.append(Paragraph(f'<b>Notes :</b> {report.observations}', body))
        if report.work_done:
            story.append(Paragraph(f'<b>Travail effectué :</b> {report.work_done}', body))
        if report.problems:
            story.append(Paragraph(f'<b>Problèmes :</b> {report.problems}', body))
        if report.objectives:
            story.append(Paragraph(f'<b>Objectifs :</b> {report.objectives}', body))

    doc.build(story)
    return buffer.getvalue()


def build_finance_pdf(*, period_label, start, end, totals, incomes, expenses, by_command_incomes=None, by_command_expenses=None, project_margins=None) -> bytes:
    """PDF A4 — rapport finance (journalier / mensuel / semestriel)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f'Finance {period_label}',
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'FinTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=15,
        spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        'FinSub',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=12,
    )
    section = ParagraphStyle(
        'FinSec',
        parent=styles['Heading2'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
    )
    small = ParagraphStyle('FinSmall', parent=styles['Normal'], fontSize=8, leading=11)

    story = [
        Paragraph('Agence Mwinda — Rapport Finance', title),
        Paragraph(
            f'{period_label}<br/>Période : {start.strftime("%d/%m/%Y")} → {end.strftime("%d/%m/%Y")}',
            subtitle,
        ),
    ]

    result_label = 'Gain / Excédent' if totals.get('is_gain') else 'Perte / Déficit'
    summary = [
        ['Total entrées', f"{totals['entrees']} $"],
        ['Total sorties', f"{totals['sorties']} $"],
        [result_label, f"{totals['solde']} $"],
    ]
    summary_table = Table(summary, colWidths=[70 * mm, 100 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#166534')),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#991b1b')),
        ('TEXTCOLOR', (1, 2), (1, 2), colors.HexColor('#166534') if totals.get('is_gain') else colors.HexColor('#991b1b')),
        ('FONTNAME', (1, 2), (1, 2), 'Helvetica-Bold'),
    ]))
    story.append(summary_table)

    def _lines_table(title_text, rows, amount_color):
        story.append(Paragraph(title_text, section))
        if not rows:
            story.append(Paragraph('Aucune écriture sur cette période.', small))
            return
        data = [['Date', 'Projet', 'Catégorie', 'Paiement', 'Libellé', 'Montant']]
        for row in rows:
            data.append([
                row['date'].strftime('%d/%m/%Y'),
                Paragraph(str(row.get('project') or row['command_reference']), small),
                Paragraph(str(row.get('category') or '—'), small),
                Paragraph(str(row.get('payment_method') or '—'), small),
                Paragraph(str(row['label']), small),
                f"{row['amount']} $",
            ])
        table = Table(data, colWidths=[20 * mm, 36 * mm, 28 * mm, 24 * mm, 42 * mm, 22 * mm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
            ('TEXTCOLOR', (5, 1), (5, -1), amount_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(table)

    income_rows = [
        {
            'date': item.income_date,
            'command_reference': item.command_reference,
            'project': item.project.name if item.project_id else '',
            'category': item.get_category_display(),
            'payment_method': item.get_payment_method_display(),
            'label': item.label,
            'amount': item.amount,
        }
        for item in incomes
    ]
    expense_rows = [
        {
            'date': item.expense_date,
            'command_reference': item.command_reference,
            'project': item.project.name if item.project_id else '',
            'category': item.get_category_display(),
            'payment_method': item.get_payment_method_display(),
            'label': item.label,
            'amount': item.amount,
        }
        for item in expenses
    ]
    _lines_table('Entrées', income_rows, colors.HexColor('#166534'))
    _lines_table('Sorties', expense_rows, colors.HexColor('#991b1b'))

    if project_margins:
        story.append(Paragraph('Marge par projet', section))
        margin_data = [['Projet', 'Entrées', 'Sorties', 'Marge']]
        for item in project_margins:
            margin_data.append([
                Paragraph(str(item['name']), small),
                f"{item['entrees']} $",
                f"{item['sorties']} $",
                f"{item['marge']} $",
            ])
        margin_table = Table(margin_data, colWidths=[80 * mm, 30 * mm, 30 * mm, 30 * mm])
        margin_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ALIGN', (1, 1), (3, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(margin_table)

    if by_command_incomes is not None or by_command_expenses is not None:
        story.append(Paragraph('Totaux par référence (hors / avec texte)', section))
        cmd_data = [['Type', 'Référence', 'Nb', 'Total']]
        for item in (by_command_incomes or []):
            cmd_data.append(['Entrée', item['command_reference'], str(item['count']), f"{item['total']} $"])
        for item in (by_command_expenses or []):
            cmd_data.append(['Sortie', item['command_reference'], str(item['count']), f"{item['total']} $"])
        if len(cmd_data) == 1:
            story.append(Paragraph('Aucun regroupement.', small))
        else:
            cmd_table = Table(cmd_data, colWidths=[25 * mm, 85 * mm, 20 * mm, 40 * mm])
            cmd_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
                ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(cmd_table)

    doc.build(story)
    return buffer.getvalue()
