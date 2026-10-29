"""UbiFleet — Outils partagés pour les tests."""

from apps.accounts.models import Agence, Role, User

NIVEAUX_ROLES = {
    'super_admin': 10,
    'dg': 8,
    'responsable_flotte': 6,
    'gestionnaire': 4,
    'comptable': 3,
    'operateur': 2,
    'chauffeur': 1,
}


class UtilisateursMixin:
    """Crée les rôles système, deux agences et un utilisateur par rôle
    dans l'agence A (self.<code_role>), plus un opérateur de l'agence B."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.roles = {
            code: Role.objects.create(code=code, nom=code, niveau=niveau, is_system=True)
            for code, niveau in NIVEAUX_ROLES.items()
        }
        cls.agence_a = Agence.objects.create(nom='Abidjan', code='ABJ', ville='Abidjan')
        cls.agence_b = Agence.objects.create(nom='Bouaké', code='BKE', ville='Bouaké')
        for code in NIVEAUX_ROLES:
            setattr(cls, code, cls.creer_utilisateur(code, code, cls.agence_a))
        cls.operateur_b = cls.creer_utilisateur('operateur_b', 'operateur', cls.agence_b)

    @classmethod
    def creer_utilisateur(cls, nom, code_role, agence):
        return User.objects.create_user(
            email=f'{nom}@test.ci', username=nom, password='Motdepasse!2026',
            first_name=nom, last_name='Test', role=cls.roles[code_role], agence=agence,
        )
