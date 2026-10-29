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
          const f = store.filters();
          const p = store.pagination();
          const params: Record<string, any> = { page: p.page, page_size: p.pageSize };
          if (f.agence)    params['agence']    = f.agence;
          if (f.annee)     params['annee']     = f.annee;
          if (f.categorie) params['categorie'] = f.categorie;
          if (f.vehicule)  params['vehicule']  = f.vehicule;
          if (f.mois)      params['mois']      = f.mois;

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

