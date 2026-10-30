"""UbiFleet — Faits marquants : API.

Consultation, création et suppression soumises aux permissions par rôle
(module « faits_marquants », réglable dans Administration › Permissions) et
cloisonnées par agence.
"""
from django.db.models import Q
from django_filters import rest_framework as df
from rest_framework import filters, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.accounts.permissions import RoleBasedPermission
from apps.core.agences import AgenceMixin, agence_pour_creation, controler_agence, voit_toutes_agences

from .models import FaitMarquant
from .serializers import FaitMarquantSerializer


class FaitMarquantFilter(df.FilterSet):
    date_debut = df.DateFilter(field_name='date', lookup_expr='gte')
    date_fin   = df.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model  = FaitMarquant
        fields = ['agence', 'date_debut', 'date_fin']


class FaitMarquantViewSet(AgenceMixin, viewsets.ModelViewSet):
    serializer_class   = FaitMarquantSerializer
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [RoleBasedPermission]
    module   = 'faits_marquants'
    role_map = {
        'list': 'operateur',
        'retrieve': 'operateur',
        'create': 'gestionnaire',
        'update': 'gestionnaire',
        'partial_update': 'gestionnaire',
        'destroy': 'responsable_flotte',
    }
    filter_backends  = [df.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = FaitMarquantFilter
    search_fields    = ['libelle', 'description']
    ordering_fields  = ['date', 'created_at']

    def get_queryset(self):
        # Faits de son agence + faits concernant toutes les agences (agence vide)
        qs = FaitMarquant.objects.select_related('agence', 'created_by')
        user = self.request.user
        if not voit_toutes_agences(user):
            qs = qs.filter(Q(agence_id=user.agence_id) | Q(agence__isnull=True))
        return qs

    def _verifier_modifiable(self, fait):
        if fait.agence_id is None and not voit_toutes_agences(self.request.user):
            raise PermissionDenied(
                "Ce fait marquant concerne toutes les agences : modification réservée "
                "aux utilisateurs « Toutes les agences ».")

    def perform_update(self, serializer):
        self._verifier_modifiable(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._verifier_modifiable(instance)
        instance.document.delete(save=False)
        instance.delete()

    def perform_create(self, serializer):
        user = self.request.user
        controler_agence(user, serializer.validated_data)
        serializer.save(created_by=user,
                        agence=agence_pour_creation(user, serializer.validated_data.get('agence')))
