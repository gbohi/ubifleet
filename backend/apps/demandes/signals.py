"""UbiFleet — Signaux du workflow des demandes."""
from django.dispatch import Signal

# Émis à la clôture d'une demande, dans la transaction de la décision.
# Arguments : demande, decision ('approuvee' | 'rejetee' | 'annulee'), utilisateur.
demande_cloturee = Signal()
