// UbiFleet — Carburant SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { CarburantApiService } from '../../core/services/api.service';
import { PleinCarburant, DotationCarburant } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

interface CarburantState {
  pleins:        PleinCarburant[];
  dotations:     DotationCarburant[];
  anomalies:     PleinCarburant[];
  stats:         any | null;
  consommation:  any[];
  loadingState:  LoadingState;
  error:         string | null;
  pagination:    PaginationState;
  filters: {
    search:            string;
    agence:            string;
    statut_validation: string;
    vehicule:          string;
    mois:              string;
    annee:             string;
  };
}

const initialState: CarburantState = {
  pleins:       [],
  dotations:    [],
  anomalies:    [],
  stats:        null,
  consommation: [],
  loadingState: 'idle',
  error:        null,
  pagination:   initialPagination,
  filters: {
    search:            '',
    agence:            '',
    statut_validation: '',
    vehicule:          '',
    mois:              '',
    annee:             '',
  },
};

export const CarburantStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:      computed(() => store.loadingState() === 'loading'),
    isLoaded:       computed(() => store.loadingState() === 'loaded'),
    hasError:       computed(() => store.loadingState() === 'error'),
    nbAnomalies:    computed(() => store.anomalies().length),
    totalVolumeL:   computed(() =>
      store.pleins().reduce((acc, p) => acc + Number(p.volume_litres), 0)
    ),
    totalMontantFCFA: computed(() =>
      store.pleins().reduce((acc, p) => acc + Number(p.montant_fcfa), 0)
    ),
    hasActiveFilters: computed(() => {
      const f = store.filters();
      return !!(f.search || f.agence || f.statut_validation || f.vehicule || f.mois || f.annee);
    }),
  })),

  withMethods((store) => {
    const api = inject(CarburantApiService);
    return {

    loadPleins: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const f = store.filters();
          const p = store.pagination();
          const params: Record<string, any> = { page: p.page, page_size: p.pageSize };
          if (f.search)            params['search']            = f.search;
          if (f.agence)            params['agence']            = f.agence;
          if (f.statut_validation) params['statut_validation'] = f.statut_validation;
          if (f.vehicule)          params['vehicule']          = f.vehicule;
          if (f.mois)              params['mois']              = f.mois;
          if (f.annee)             params['annee']             = f.annee;

          return api.getPleins(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                pleins:       Array.isArray(res) ? res : (res.results ?? []),
                loadingState: 'loaded',
                pagination:   { ...store.pagination(), total: res.count },
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.error?.detail ?? 'Erreur chargement carburant.',
              }),
            })
          );
        })
      )
    ),

    loadStats: rxMethod<{ mois?: string; annee?: string; agence?: string }>(
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

    loadAnomalies: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getAnomalies().pipe(
            tapResponse({
              next: (res: any) => patchState(store, { anomalies: res.results ?? res }),
              error: () => {},
            })
          )
        )
      )
    ),

    loadConsommation: rxMethod<Record<string, any>>(
      pipe(
        switchMap((params) =>
          api.getConsommation(params).pipe(
            tapResponse({
              next: (data) => patchState(store, { consommation: data }),
              error: () => {},
            })
          )
        )
      )
    ),

    loadDotations: rxMethod<{ vehicule?: string; mois?: string; annee?: string }>(
      pipe(
        switchMap((params) =>
          api.getDotations(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                dotations: Array.isArray(res) ? res : (res.results ?? []),
              }),
              error: () => {},
            })
          )
        )
      )
    ),

    setFilter(key: keyof CarburantState['filters'], value: string): void {
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

