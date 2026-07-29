from django.db import models
from django.conf import settings

from projects.branches import TECH_BRANCH_CHOICES

# Create your models here.

class DailyReport(models.Model):
    DEPARTMENT_CHOICES = TECH_BRANCH_CHOICES

    ASSEMBLY_METHOD_CHOICES = (
        ('colle', 'Colle'),
        ('vis', 'Vis'),
        ('rivets', 'Rivets'),
        ('soudure', 'Soudure'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    date = models.DateField()

    # Nouveaux champs selon la fiche
    department = models.CharField(max_length=50, choices=TECH_BRANCH_CHOICES, blank=True)
    project = models.CharField(max_length=100, blank=True)
    team_agent = models.CharField(max_length=100, blank=True)

    # 1. CONCEPTION
    conception_brief_received = models.BooleanField(default=False)
    conception_croquis_validated = models.BooleanField(default=False)
    conception_modeling_done = models.BooleanField(default=False)
    conception_file_ready = models.BooleanField(default=False)

    # 2. DÉCOUPE
    decoupe_bois_decoupe = models.BooleanField(default=False)
    decoupe_metal_decoupe = models.BooleanField(default=False)
    decoupe_pvc_decoupe = models.BooleanField(default=False)
    decoupe_dimensions_verified = models.BooleanField(default=False)

    # 3. ASSEMBLAGE
    assemblage_method = models.CharField(max_length=20, choices=ASSEMBLY_METHOD_CHOICES, blank=True)
    assemblage_partial = models.BooleanField(default=False)
    assemblage_complete = models.BooleanField(default=False)
    assemblage_renforts = models.BooleanField(default=False)

    # 4. INSTALLATION LED
    led_bande_posee = models.BooleanField(default=False)
    led_alimentation_installee = models.BooleanField(default=False)
    led_test_allumage = models.BooleanField(default=False)
    led_cablage_secure = models.BooleanField(default=False)

    # 5. CONTRÔLE QUALITÉ
    qualite_alignement = models.BooleanField(default=False)
    qualite_solidite = models.BooleanField(default=False)
    qualite_finitions = models.BooleanField(default=False)
    qualite_conformite = models.BooleanField(default=False)
    qualite_validation = models.BooleanField(default=False)

    # 6. PEINTURE & FINITION
    peinture_poncage = models.BooleanField(default=False)
    peinture_sous_couche = models.BooleanField(default=False)
    peinture_peinture = models.BooleanField(default=False)
    peinture_vernis = models.BooleanField(default=False)
    peinture_nettoyage = models.BooleanField(default=False)

    # 7. LIVRAISON / INSTALLATION
    livraison_emballage = models.BooleanField(default=False)
    livraison_transport = models.BooleanField(default=False)
    livraison_installation = models.BooleanField(default=False)
    livraison_rapport_photo = models.BooleanField(default=False)
    livraison_projet_cloture = models.BooleanField(default=False)

    # OBSERVATIONS
    observations = models.TextField(blank=True)

    # Anciens champs (pour compatibilité)
    work_done = models.TextField(blank=True)
    problems = models.TextField(blank=True)
    objectives = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rapport de {self.user} - {self.date}"


class FinanceExpense(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='finance_expenses',
    )
    expense_date = models.DateField()
    command_reference = models.CharField(max_length=120)
    label = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-expense_date', '-created_at')

    def __str__(self):
        return f"{self.command_reference} - {self.amount} ({self.expense_date})"


class FinanceIncome(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='finance_incomes',
    )
    income_date = models.DateField()
    command_reference = models.CharField(max_length=120)
    label = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-income_date', '-created_at')

    def __str__(self):
        return f"{self.command_reference} - {self.amount} ({self.income_date})"