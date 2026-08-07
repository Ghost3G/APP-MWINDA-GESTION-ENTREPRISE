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


PAYMENT_METHOD_CHOICES = (
    ('cash', 'Espèces'),
    ('mobile_money', 'Mobile Money'),
    ('virement', 'Virement'),
    ('cheque', 'Chèque'),
    ('autre', 'Autre'),
)

INCOME_CATEGORY_CHOICES = (
    ('acompte', 'Acompte client'),
    ('solde', 'Solde client'),
    ('prestation', 'Prestation / service'),
    ('autre', 'Autre encaissement'),
)

EXPENSE_CATEGORY_CHOICES = (
    ('materiaux', 'Matériaux / fournitures'),
    ('sous_traitance', 'Sous-traitance'),
    ('transport', 'Transport / livraison'),
    ('salaires', 'Salaires / primes'),
    ('loyer', 'Loyer / charges'),
    ('admin', 'Frais administratifs'),
    ('marketing', 'Marketing / com'),
    ('autre', 'Autre dépense'),
)


class FinanceClient(models.Model):
    """Fiche client CRM — collée au portefeuille d'un commercial."""

    code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='Code client',
        help_text='Format CLI-XX-0001 (initiales commercial + numéro).',
    )
    name = models.CharField(max_length=200, verbose_name='Nom / Société')
    contact_name = models.CharField(max_length=150, blank=True, verbose_name='Personne de contact')
    phone = models.CharField(max_length=40, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True, verbose_name='Email')
    address = models.CharField(max_length=255, blank=True, verbose_name='Adresse')
    city = models.CharField(max_length=100, blank=True, verbose_name='Ville')
    country = models.CharField(max_length=100, blank=True, default='RDC', verbose_name='Pays')
    tax_id = models.CharField(max_length=80, blank=True, verbose_name='NIF / RCCM')
    notes = models.TextField(blank=True, verbose_name='Notes')
    status = models.CharField(
        max_length=20,
        choices=(
            ('prospect', 'Prospect'),
            ('active', 'Actif'),
            ('inactive', 'Inactif'),
            ('lost', 'Perdu'),
        ),
        default='prospect',
        db_index=True,
        verbose_name='Statut',
    )
    next_action = models.CharField(max_length=255, blank=True, verbose_name='Prochaine action')
    next_action_date = models.DateField(null=True, blank=True, verbose_name='Date prochaine action')
    commercial_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_clients',
        verbose_name='Commercial responsable',
        help_text='Agent commercial propriétaire du portefeuille.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_clients_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name', 'id')
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        if self.code:
            return f"{self.code} — {self.name}"
        return self.name


class CrmFollowUp(models.Model):
    """Note / relance commerciale sur un client."""

    TYPE_CHOICES = (
        ('note', 'Note'),
        ('call', 'Appel'),
        ('meeting', 'RDV'),
        ('email', 'Email'),
        ('other', 'Autre'),
    )

    client = models.ForeignKey(
        FinanceClient,
        on_delete=models.CASCADE,
        related_name='follow_ups',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_follow_ups',
    )
    follow_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='note')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.client_id} — {self.follow_type}"


class FinanceExpense(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='finance_expenses',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_expenses',
    )
    client = models.ForeignKey(
        FinanceClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_expenses',
    )
    expense_date = models.DateField()
    command_reference = models.CharField(max_length=120)
    label = models.CharField(max_length=180)
    category = models.CharField(
        max_length=40,
        choices=EXPENSE_CATEGORY_CHOICES,
        default='autre',
    )
    payment_method = models.CharField(
        max_length=40,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to='finance_attachments/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Justificatif',
    )
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
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_incomes',
    )
    client = models.ForeignKey(
        FinanceClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_incomes',
    )
    income_date = models.DateField()
    command_reference = models.CharField(max_length=120)
    label = models.CharField(max_length=180)
    category = models.CharField(
        max_length=40,
        choices=INCOME_CATEGORY_CHOICES,
        default='autre',
    )
    payment_method = models.CharField(
        max_length=40,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to='finance_attachments/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Justificatif',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-income_date', '-created_at')

    def __str__(self):
        return f"{self.command_reference} - {self.amount} ({self.income_date})"


class FinanceDayClosure(models.Model):
    """Journée de caisse verrouillée : plus de saisie / modification / suppression."""

    closure_date = models.DateField(unique=True, db_index=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_day_closures',
    )
    closed_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ('-closure_date',)

    def __str__(self):
        return f"Clôture caisse {self.closure_date}"