"""UbiFleet — Accounts Serializers"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .models import User, Agence, Role, PermissionRole
from .permissions import can_assign_role


class AgenceSerializer(serializers.ModelSerializer):
    nb_vehicules = serializers.SerializerMethodField()

    class Meta:
        model  = Agence
        fields = [
            'id', 'nom', 'code', 'ville', 'adresse',
            'telephone', 'responsable_nom',
            'numero_client_total',
            'is_active', 'nb_vehicules', 'created_at'
        ]

    def get_nb_vehicules(self, obj):
        return obj.vehicules.filter(is_active=True).count()


class RoleSerializer(serializers.ModelSerializer):
    nb_utilisateurs = serializers.SerializerMethodField()

    class Meta:
        model  = Role
        fields = [
            'id', 'code', 'nom', 'description', 'niveau',
            'is_active', 'is_system', 'nb_utilisateurs',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'is_system']

    def get_nb_utilisateurs(self, obj):
        return obj.utilisateurs.filter(is_active=True).count()

    def validate_code(self, value):
        # Le code ne peut pas être modifié après création
        if self.instance and self.instance.code != value:
            raise serializers.ValidationError(
                "Le code d'un rôle ne peut pas être modifié après création."
            )
        return value

    def validate_niveau(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError("Le niveau doit être entre 1 et 10.")
        return value


class UserSerializer(serializers.ModelSerializer):
    agence_detail = AgenceSerializer(source='agence', read_only=True)
    role_detail   = RoleSerializer(source='role', read_only=True)
    full_name     = serializers.CharField(read_only=True)

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'role', 'role_detail', 'agence', 'agence_detail',
            'telephone', 'avatar', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']


class RoleAssignmentMixin:
    """Refuse l'attribution d'un rôle de niveau égal ou supérieur à celui
    de l'utilisateur connecté (hors super admin)."""

    def validate_role(self, value):
        request = self.context.get('request')
        if request and not can_assign_role(request.user, value):
            raise serializers.ValidationError(
                "Vous ne pouvez pas attribuer un rôle de niveau égal ou supérieur au vôtre."
            )
        return value


class UserCreateSerializer(RoleAssignmentMixin, serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = [
            'email', 'username', 'first_name', 'last_name',
            'password', 'password2', 'role', 'agence', 'telephone',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password2'):
            raise serializers.ValidationError(
                {"password": "Les mots de passe ne correspondent pas."}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(RoleAssignmentMixin, serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = [
            'email', 'username', 'first_name', 'last_name',
            'role', 'agence', 'telephone', 'is_active',
        ]


class ResetProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'telephone', 'avatar', 'username']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect.")
        return value


class PermissionRoleSerializer(serializers.ModelSerializer):
    role_nom    = serializers.CharField(source='role.nom', read_only=True)
    role_niveau = serializers.IntegerField(source='role.niveau', read_only=True)
    module_display = serializers.CharField(source='get_module_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model  = PermissionRole
        fields = [
            'id', 'role', 'role_nom', 'role_niveau',
            'module', 'module_display',
            'action', 'action_display', 'autorise',
        ]


class UbiFleetTokenObtainSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email']       = user.email
        token['full_name']   = user.full_name
        token['role_code']   = user.role.code if user.role else None
        token['role_nom']    = user.role.nom if user.role else None
        token['role_niveau'] = user.role.niveau if user.role else 0
        token['agence_id']   = str(user.agence_id) if user.agence_id else None
        token['agence_nom']  = user.agence.nom if user.agence else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
