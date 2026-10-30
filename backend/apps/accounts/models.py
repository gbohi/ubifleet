"""UbiFleet — Accounts Models (rôles 100% dynamiques)"""

from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class Agence(models.Model):
    """Agence / site Ubipharm."""
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom             = models.CharField(max_length=100, verbose_name="Nom de l'agence")
    code            = models.CharField(max_length=10, unique=True, verbose_name="Code agence")
    ville           = models.CharField(max_length=100)
    adresse         = models.TextField(blank=True)
    telephone       = models.CharField(max_length=20, blank=True)
    responsable_nom = models.CharField(max_length=150, blank=True)
    numero_client_total = models.CharField(
        max_length=50, blank=True,
        verbose_name="N° client Total",
        help_text="Identifiant client dans la plateforme TotalEnergies — "
                  "sert à réconcilier les transactions importées avec cette agence."
    )
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Agence"
        verbose_name_plural = "Agences"
        ordering            = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code})"


class Role(models.Model):
    """
    Rôle UbiFleet — 100% dynamique, créé/modifié depuis l'UI.

    Le champ `niveau` détermine la hiérarchie :
    plus le niveau est élevé, plus le rôle est puissant.
    Le niveau 10 est réservé au super administrateur.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code        = models.SlugField(
        max_length=50, unique=True,
        help_text="Identifiant technique unique (ex: responsable_flotte). "
                  "Ne peut pas être modifié après création."
    )
    nom         = models.CharField(max_length=100, verbose_name="Nom du rôle")
    description = models.TextField(blank=True)
    niveau      = models.PositiveSmallIntegerField(
        default=1,
        help_text="Niveau hiérarchique (1=le plus bas, 10=super admin). "
                  "Détermine quelles actions sont autorisées par défaut."
    )
    is_active   = models.BooleanField(default=True)
    is_system   = models.BooleanField(
        default=False,
        help_text="Rôle système — ne peut pas être supprimé."
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Rôle"
        verbose_name_plural = "Rôles"
        ordering            = ['-niveau', 'nom']

    def __str__(self):
        return f"{self.nom} (niveau {self.niveau})"

    @property
    def is_super_admin(self):
        return self.niveau >= 10


class User(AbstractUser):
    """Utilisateur UbiFleet."""

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email     = models.EmailField(unique=True)
    role      = models.ForeignKey(
        Role, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='utilisateurs',
        verbose_name="Rôle"
    )
    agence    = models.ForeignKey(
        Agence, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='utilisateurs',
        verbose_name="Agence"
    )
    telephone = models.CharField(max_length=20, blank=True)
    avatar    = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Désactiver les M2M groupes et permissions Django
    groups = None
    user_permissions = None

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name        = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        default_permissions = ()

    def __str__(self):
        role_nom = self.role.nom if self.role else 'Sans rôle'
        return f"{self.get_full_name()} ({role_nom})"

    @property
    def full_name(self):
        return self.get_full_name() or self.email

    @property
    def role_code(self):
        """Code du rôle pour les comparaisons rapides."""
        return self.role.code if self.role else ''

    @property
    def role_niveau(self):
        """Niveau hiérarchique du rôle."""
        return self.role.niveau if self.role else 0

    @property
    def is_super_admin(self):
        return self.role.is_super_admin if self.role else False

    def has_min_niveau(self, niveau: int) -> bool:
        return self.role_niveau >= niveau

    def is_admin_level(self) -> bool:
        """Responsable flotte ou supérieur (niveau >= 6)."""
        return self.role_niveau >= 6


class PermissionRole(models.Model):
    """
    Permission configurable par rôle, module et action.
    Stockée en DB, modifiable depuis l'UI.
    """

    MODULES = [
        ('vehicules',    'Véhicules'),
        ('carburant',    'Carburant'),
        ('entretien',    'Entretien'),
        ('sinistres',    'Sinistres'),
        ('budget',       'Budget'),
        ('chauffeurs',   'Chauffeurs'),
        ('releves_km',   'Relevés Km'),
        ('affectations', 'Affectations'),
        ('alertes',      'Alertes'),
        ('controle',     'Contrôle Véhicule'),
        ('demandes',     'Demandes'),
        ('users',        'Utilisateurs'),
        ('roles',        'Rôles'),
        ('permissions',  'Permissions'),
        ('agences',      'Agences'),
        ('parametres',   'Paramètres'),
        ('total_import',  'Import Total Carburant'),
        ('faits_marquants', 'Faits marquants'),
    ]

    # Actions globales (union de toutes les actions possibles)
    ACTIONS = [
        ('list',                    'Consulter (liste)'),
        ('retrieve',                'Consulter (détail)'),
        ('create',                  'Créer'),
        ('update',                  'Modifier'),
        ('partial_update',          'Modifier (partiel)'),
        ('destroy',                 'Supprimer'),
        ('valider',                 'Valider une prise de carburant'),
        ('anomalies',               'Voir anomalies'),
        ('demarrer',                'Démarrer intervention'),
        ('terminer',                'Terminer intervention'),
        ('changer_statut',          'Changer statut'),
        ('kilometrage',             'Mettre à jour km'),
        ('changer_immatriculation', 'Changer immatriculation'),
        ('tableau_de_bord',         'Tableau de bord budget'),
        ('toggle_active',           'Activer/désactiver utilisateur'),
        ('reset_password',          'Réinitialiser mot de passe'),
        ('valider_fiche',           'Valider une fiche de contrôle'),
        ('bulk_save',               'Sauvegarder points de contrôle'),
        ('soumettre',               'Soumettre une demande'),
        ('valider_demande',         'Valider une demande'),
        ('rejeter',                 'Rejeter une demande'),
        ('annuler',                 'Annuler une demande'),
        ('saisie_hors_delai',       'Saisie hors délai (hors fenêtre de saisie)'),
        ('cloturer_tournee',        'Clôturer une tournée'),
        ('rouvrir_tournee',         'Rouvrir une tournée clôturée'),
        ('annuler_tournee',         'Annuler une tournée'),
    ]

    # Actions par module — utilisé dans l'UI pour n'afficher que les actions pertinentes
    MODULE_ACTIONS = {
        'vehicules':    ['list','retrieve','create','update','partial_update','destroy',
                         'kilometrage','changer_immatriculation'],
        'carburant':    ['list','retrieve','create','update','partial_update','destroy',
                         'anomalies','saisie_hors_delai',
                         'cloturer_tournee','rouvrir_tournee','annuler_tournee'],
        'entretien':    ['list','retrieve','create','update','partial_update','destroy',
                         'demarrer','terminer'],
        'sinistres':    ['list','retrieve','create','update','partial_update','destroy',
                         'changer_statut'],
        'budget':       ['list','retrieve','create','update','partial_update','destroy',
                         'tableau_de_bord'],
        'chauffeurs':   ['list','retrieve','create','update','partial_update','destroy'],
        'releves_km':   ['list','retrieve','create','update','partial_update','destroy',
                         'saisie_hors_delai'],
        'affectations': ['list','retrieve','create','update','partial_update','destroy'],
        'alertes':      ['list','retrieve'],
        'controle':     ['list','retrieve','create','update','partial_update','destroy',
                         'valider_fiche','bulk_save'],
        'demandes':     ['list','retrieve','create','update','partial_update',
                         'soumettre','valider_demande','rejeter','annuler'],
        'users':        ['list','retrieve','create','update','partial_update','destroy',
                         'toggle_active','reset_password'],
        'roles':        ['list','retrieve','create','update','partial_update','destroy'],
        'permissions':  ['list','retrieve','create','update','partial_update','destroy'],
        'agences':      ['list','retrieve','create','update','partial_update','destroy'],
        'parametres':   ['list','retrieve','create','update','partial_update','destroy'],
        'total_import':  ['list','retrieve','upload','stats'],
        'faits_marquants': ['list','retrieve','create','update','partial_update','destroy'],
    }

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role     = models.ForeignKey(
        Role, on_delete=models.CASCADE,
        related_name='permissions',
        verbose_name="Rôle"
    )
    module   = models.CharField(max_length=50, choices=MODULES)
    action   = models.CharField(max_length=50, choices=ACTIONS)
    autorise = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Permission par rôle'
        verbose_name_plural = 'Permissions par rôle'
        unique_together     = [('role', 'module', 'action')]
        ordering            = ['role__niveau', 'module', 'action']

    def __str__(self):
        etat = '✓' if self.autorise else '✗'
        return f"{etat} {self.role.nom} / {self.get_module_display()} / {self.get_action_display()}"
