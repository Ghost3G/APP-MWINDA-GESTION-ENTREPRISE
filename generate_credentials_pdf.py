#!/usr/bin/env python3
"""Génère le PDF des identifiants MWINDA."""
from datetime import date
from pathlib import Path

from fpdf import FPDF

from seed_demo_data import PERSONNEL, role_for_grade, slug_email

OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = OUTPUT_DIR / 'Liste_comptes_MWINDA.pdf'
FONT_REGULAR = '/System/Library/Fonts/Supplemental/Arial.ttf'
FONT_BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'


class CredentialsPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.set_text_color(17, 24, 39)
        self.cell(0, 10, 'AGENCE MWINDA — Liste des comptes application', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Arial', '', 9)
        self.set_text_color(107, 114, 128)
        self.cell(0, 6, f'Document confidentiel — généré le {date.today().strftime("%d/%m/%Y")}', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font('Arial', '', 8)
        self.set_text_color(156, 163, 175)
        self.cell(0, 8, f'Page {self.page_no()}', align='C')


def access_label(person):
    role = role_for_grade(person['grade'], person)
    if role == 'admin':
        return 'Accès complet (Admin)'
    if role == 'directeur':
        return 'Accès complet (Directeur)'
    return 'Accès limité (Agent)'


def build_pdf():
    pdf = CredentialsPDF(orientation='L', unit='mm', format='A4')
    pdf.add_font('Arial', '', FONT_REGULAR)
    pdf.add_font('Arial', 'B', FONT_BOLD)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    col_widths = [52, 38, 52, 34, 38, 42]
    headers = ['Nom complet', 'Identifiant', 'Email', 'Mot de passe', 'Mention', 'Accès']

    pdf.set_fill_color(253, 224, 71)
    pdf.set_text_color(17, 24, 39)
    pdf.set_font('Arial', 'B', 9)
    for header, width in zip(headers, col_widths):
        pdf.cell(width, 8, header, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font('Arial', '', 8.5)
    for index, person in enumerate(PERSONNEL):
        full_name = f"{person['first_name']} {person['last_name']}"
        row = [
            full_name,
            person['username'],
            slug_email(person['username']),
            person['password'],
            person['grade'],
            access_label(person),
        ]
        if index % 2 == 0:
            pdf.set_fill_color(249, 250, 251)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(31, 41, 55)
        for value, width in zip(row, col_widths):
            pdf.cell(width, 8, value, border=1, fill=True)
        pdf.ln()

    pdf.ln(6)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 7, 'Instructions', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(55, 65, 81)
    instructions = [
        'URL de connexion : http://127.0.0.1:8000/login/ (ou l\'adresse de votre serveur MWINDA)',
        'Chaque collaborateur utilise son identifiant et son mot de passe personnel.',
        'Les directeurs et l\'administrateur ont un accès complet. Les agents ont un accès limité.',
        'Conservez ce document en lieu sûr. Changez les mots de passe après la première connexion si nécessaire.',
    ]
    for line in instructions:
        pdf.multi_cell(0, 5, f'• {line}', new_x='LMARGIN', new_y='NEXT')

    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == '__main__':
    path = build_pdf()
    print(f'PDF généré : {path}')
