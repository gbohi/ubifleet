// UbiFleet — Entretien SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { EntretienApiService } from '../../core/services/api.service';
import { Intervention, SuiviPneus } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

interface EntretienState {
  interventions:   Intervention[];
  planifiees:      Intervention[];
  pneusAChanger:   SuiviPneus[];
  stats:           any | null;
  loadingState:    LoadingState;
  error:           string | null;
  pagination:      PaginationState;
  filters: {
    search:   string;
    agence:   string;
    statut:   string;
    priorite: string;
    vehicule: string;
  };
}

const initialState: EntretienState = {
  interventions:  [],
  planifiees:     [],
  pneusAChanger:  [],
  stats:          null,
  loadingState:   'idle',
  error:          null,
  pagination:     initialPagination,
  filters: {
    search:   '',
    agence:   '',
    statut:   '',
    priorite: '',
    vehicule: '',
  },
};

export const EntretienStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:        computed(() => store.loadingState() === 'loading'),
    isLoaded:         computed(() => store.loadingState() === 'loaded'),
    hasError:         computed(() => store.loadingState() === 'error'),
    nbPlanifiees:     computed(() => store.planifiees().length),
    nbUrgentes:       computed(() =>
      store.interventions().filter(i =>
        i.priorite === 'critique' && i.statut === 'planifie'
      ).length
    ),
    coutTotalEstime:  computed(() =>
      store.interventions().reduce((acc, i) => acc + Number(i.cout_estime), 0)
    ),
  })),

  withMethods((store) => {
    const api = inject(EntretienApiService);
    return {

    loadInterventions: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const f = store.filters();
          const p = store.pagination();
          const params: Record<string, any> = { page: p.page, page_size: p.pageSize };
          if (f.search)   params['search']   = f.search;
          if (f.agence)   params['agence']   = f.agence;
          if (f.statut)   params['statut']   = f.statut;
          if (f.priorite) params['priorite'] = f.priorite;
          if (f.vehicule) params['vehicule'] = f.vehicule;

          return api.getInterventions(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                interventions: Array.isArray(res) ? res : (res.results ?? []),
                loadingState:  'loaded',
                pagination:    { ...store.pagination(), total: res.count },
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.error?.detail ?? 'Erreur chargement entretiens.',
              }),
            })
          );
        })
      )
    ),

    loadPlanifiees: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getPlanifiees().pipe(
            tapResponse({
              next: (data) => patchState(store, { planifiees: data }),
              error: () => {},
            })
          )
        )
      )
    ),

    loadPneusAChanger: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getPneusAChanger().pipe(
            tapResponse({
              next: (data) => patchState(store, { pneusAChanger: data }),
              error: () => {},
            })
          )
        )
      )
    ),

    loadStats: rxMethod<{ mois?: string; annee?: string }>(
      pipe(
        switchMap((params) =>
          api.getStats(params).pipe(
            tapResponse({
              next: (stats) => patchState(store, { stats }),
              error: () => {},
            })
          )
        )
      )
    ),

    setFilter(key: keyof EntretienState['filters'], value: string): void {
      patchState(store, {
        filters:    { ...store.filters(), [key]: value },
        pagination: { ...store.pagination(), page: 1 },
      });
    },

    resetFilters(): void {
      patchState(store, {
        filters:    initialState.filters,
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

