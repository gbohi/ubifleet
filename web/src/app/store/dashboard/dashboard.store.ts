// UbiFleet — Dashboard SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { RapportApiService } from '../../core/services/api.service';
import { DashboardData } from '../../core/models';
import { LoadingState } from '../store.utils';

interface DashboardState {
  data:         DashboardData | null;
  loadingState: LoadingState;
  error:        string | null;
  periode: {
    mois:  number;
    annee: number;
  };
  agenceFilter: string;
}

const now = new Date();

const initialState: DashboardState = {
  data:         null,
  loadingState: 'idle',
  error:        null,
  periode: {
    mois:  now.getMonth() + 1,
    annee: now.getFullYear(),
  },
  agenceFilter: '',
};

export const DashboardStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:  computed(() => store.loadingState() === 'loading'),
    isLoaded:   computed(() => store.loadingState() === 'loaded'),
    hasError:   computed(() => store.loadingState() === 'error'),

    // KPIs principaux
    nbVehicules:       computed(() => store.data()?.parc.total          ?? 0),
    nbEnService:       computed(() => store.data()?.parc.en_service      ?? 0),
    nbEnRevision:      computed(() => store.data()?.parc.en_revision     ?? 0),
    nbImmobilises:     computed(() => store.data()?.parc.immobilises     ?? 0),

    volumeCarburant:   computed(() => store.data()?.carburant.volume     ?? 0),
    montantCarburant:  computed(() => store.data()?.carburant.montant    ?? 0),
    consoMoyenne:      computed(() => store.data()?.carburant.conso_moy  ?? 0),
    nbAnomaliesCarb:   computed(() => store.data()?.carburant.anomalies  ?? 0),

    nbEntretiensPlani: computed(() => store.data()?.entretien.planifiees ?? 0),
    nbEntretiensTermi: computed(() => store.data()?.entretien.terminees  ?? 0),
    coutEntretien:     computed(() => store.data()?.entretien.cout       ?? 0),

    nbSinistresEnCours:computed(() => store.data()?.sinistres.en_cours   ?? 0),
    nbAlertesActives:  computed(() => store.data()?.alertes.total        ?? 0),
    nbAlertesCritiques:computed(() => store.data()?.alertes.critiques    ?? 0),

    assurancesCritiques: computed(() => store.data()?.assurances_critiques ?? 0),

    // Données graphiques
    coutMensuelChart:  computed(() => store.data()?.cout_mensuel          ?? []),
    topConsommation:   computed(() => store.data()?.top_consommation       ?? []),
    /** Véhicules qui consomment le plus au-dessus de leur référence (conso pondérée par les km). */
    topEcartConso:     computed(() => store.data()?.top_ecart_conso        ?? []),
    repartitionCouts:  computed(() => store.data()?.repartition_couts      ?? []),

    // Libellé période
    periodLabel: computed(() => {
      const moisNoms = [
        'Janvier','Février','Mars','Avril','Mai','Juin',
        'Juillet','Août','Septembre','Octobre','Novembre','Décembre'
      ];
      const p = store.periode();
      return `${moisNoms[p.mois - 1]} ${p.annee}`;
    }),
  })),

  withMethods((store) => {
    const rapportApi = inject(RapportApiService);
    return {

    // Charger toutes les données du dashboard
    loadDashboard: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const { mois, annee } = store.periode();
          const params: Record<string, any> = { mois, annee };
          if (store.agenceFilter()) params['agence'] = store.agenceFilter();

          return rapportApi.getDashboard(params).pipe(
            tapResponse({
              next: (data) => patchState(store, {
                data,
                loadingState: 'loaded',
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.status === 0
                  ? 'Serveur inaccessible. Vérifiez que le backend Django est démarré.'
                  : err?.error?.detail ?? 'Erreur chargement tableau de bord.',
              }),
            })
          );
        })
      )
    ),

    // Changer la période
    setPeriode(mois: number, annee: number): void {
      patchState(store, { periode: { mois, annee } });
    },

    // Changer l'agence filtrée
    setAgenceFilter(agenceId: string): void {
      patchState(store, { agenceFilter: agenceId });
    },

    clearError(): void {
      patchState(store, { error: null });
    },
    };
  })
);

