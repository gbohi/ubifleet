// UbiFleet — Budget SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { BudgetApiService } from '../../core/services/api.service';
import { BudgetAnnuel, Depense } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

interface BudgetState {
  budgets:        BudgetAnnuel[];
  depenses:       Depense[];
  tableauDeBord:  any | null;
  loadingState:   LoadingState;
  error:          string | null;
  pagination:     PaginationState;
  filters: {
    agence:    string;
    annee:     string;
    categorie: string;
    vehicule:  string;
    mois:      string;
  };
  /** Filtres de l'état des dépenses (onglet Dépenses), indépendants du tableau de bord. */
  filtresDepenses: FiltresDepenses;
  /** Récapitulatif de l'état des dépenses (totaux par poste, catégorie, origine). */
  etat: EtatDepenses | null;
}

export interface FiltresDepenses {
  date_min: string; date_max: string; categorie: string; poste: string;
  origine: string; agence: string; vehicule: string; recherche: string;
}
export interface LigneEtat { libelle: string; nb: number; total: number; part: number; [cle: string]: any; }
export interface EtatDepenses {
  total: number; nb: number;
  par_categorie: LigneEtat[]; par_poste: LigneEtat[]; par_origine: LigneEtat[];
}

export const filtresDepensesInitiaux = (): FiltresDepenses => ({
  date_min: `${new Date().getFullYear()}-01-01`, date_max: '', categorie: '', poste: '',
  origine: '', agence: '', vehicule: '', recherche: '',
});

/** Paramètres d'API des filtres renseignés. */
export function paramsDepenses(f: FiltresDepenses): Record<string, string> {
  return Object.fromEntries(Object.entries(f).filter(([, v]) => v !== '' && v != null));
}

const initialState: BudgetState = {
  budgets:       [],
  depenses:      [],
  tableauDeBord: null,
  loadingState:  'idle',
  error:         null,
  pagination:    initialPagination,
  filters: {
    agence:    '',
    annee:     String(new Date().getFullYear()),
    categorie: '',
    vehicule:  '',
    mois:      '',
  },
  filtresDepenses: filtresDepensesInitiaux(),
  etat: null,
};

export const BudgetStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:    computed(() => store.loadingState() === 'loading'),
    isLoaded:     computed(() => store.loadingState() === 'loaded'),
    hasError:     computed(() => store.loadingState() === 'error'),
    totalRealise: computed(() => store.tableauDeBord()?.total_realise ?? 0),
    parCategorie: computed(() => store.tableauDeBord()?.par_categorie ?? []),
    parMois:      computed(() => store.tableauDeBord()?.par_mois      ?? []),
    parAgence:    computed(() => store.tableauDeBord()?.par_agence     ?? []),
    topVehicules: computed(() => store.tableauDeBord()?.top_vehicules  ?? []),
  })),

  withMethods((store) => {
    const api = inject(BudgetApiService);
    return {

    loadTableauDeBord: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const f = store.filters();
          const params: Record<string, any> = {};
          if (f.annee)  params['annee']  = f.annee;
          if (f.agence) params['agence'] = f.agence;

          return api.getTableauDeBord(params).pipe(
            tapResponse({
              next: (data) => patchState(store, {
                tableauDeBord: data,
                loadingState:  'loaded',
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.error?.detail ?? 'Erreur chargement budget.',
              }),
            })
          );
        })
      )
    ),

    loadDepenses: rxMethod<void>(
      pipe(
        switchMap(() => {
          const p = store.pagination();
          const params: Record<string, any> = { ...paramsDepenses(store.filtresDepenses()), page: p.page, page_size: p.pageSize };

          return api.getDepenses(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                depenses:  Array.isArray(res) ? res : (res.results ?? []),
                pagination: { ...store.pagination(), total: res.count },
              }),
              error: () => {},
            })
          );
        })
      )
    ),

    loadEtat: rxMethod<void>(
      pipe(
        switchMap(() => api.getEtatDepenses(paramsDepenses(store.filtresDepenses())).pipe(
          tapResponse({
            next: (etat) => patchState(store, { etat }),
            error: () => patchState(store, { etat: null }),
          })
        ))
      )
    ),

    setFiltresDepenses(f: FiltresDepenses): void {
      patchState(store, { filtresDepenses: { ...f }, pagination: { ...store.pagination(), page: 1 } });
    },

    setFilter(key: keyof BudgetState['filters'], value: string): void {
      patchState(store, {
        filters:    { ...store.filters(), [key]: value },
        pagination: { ...store.pagination(), page: 1 },
      });
    },

    setPage(page: number): void {
      patchState(store, { pagination: { ...store.pagination(), page } });
    },

    clearError(): void {
      patchState(store, { error: null });
    },
    };
  })
);

