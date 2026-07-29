"""Branches du département technique MWINDA."""

TECH_BRANCH_CHOICES = (
    ('metal_design', 'METAL DESIGN'),
    ('wood_design', 'WOOD DESIGN'),
    ('branding', 'BRANDING'),
    ('signaletique', 'Signalétique'),
    ('gravure', 'Gravure'),
    ('design_rd_innovation', 'DESIGN RD & INNOVATION'),
)

TECH_DEPARTMENT_LABEL = 'Département Technique'

LEGACY_DIRECTION_MAP = {
    'design': 'wood_design',
    'marketing': 'branding',
    'finance': 'gravure',
    'technique': 'metal_design',
    'signalétique': 'signaletique',
}


def get_branch_label(branch):
    return dict(TECH_BRANCH_CHOICES).get(branch, branch)


def normalize_branch(value):
    if not value:
        return 'metal_design'
    if value in dict(TECH_BRANCH_CHOICES):
        return value
    return LEGACY_DIRECTION_MAP.get(value, 'metal_design')


def is_valid_branch(value):
    return value in dict(TECH_BRANCH_CHOICES)
