// UbiFleet — Chauffeurs SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { ChauffeurApiService } from '../../core/services/api.service';
import { Chauffeur } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

interface ChauffeursState {
  chauffeurs:      Chauffeur[];
  permisExpirant:  Chauffeur[];
  loadingState:    LoadingState;
  error:           string | null;
  pagination:      PaginationState;
  filters: {
    search:  string;
    agence:  string;
    statut:  string;
  };
}

const initialState: ChauffeursState = {
  chauffeurs:     [],
  permisExpirant: [],
  loadingState:   'idle',
  error:          null,
  pagination:     initialPagination,
  filters: { search: '', agence: '', statut: '' },
};

export const ChauffeursStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:       computed(() => store.loadingState() === 'loading'),
    isLoaded:        computed(() => store.loadingState() === 'loaded'),
    hasError:        computed(() => store.loadingState() === 'error'),
    nbActifs:        computed(() =>
      store.chauffeurs().filter(c => c.statut === 'actif').length
    ),
    nbPermisUrgents: computed(() =>
      store.permisExpirant().filter(c =>
        c.jours_expiration_permis !== null && c.jours_expiration_permis <= 30
      ).length
    ),
  })),

  withMethods((store) => {
    const api = inject(ChauffeurApiService);
    return {

    loadChauffeurs: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const f = store.filters();
          const p = store.pagination();
          const params: Record<string, any> = { page: p.page, page_size: p.pageSize };
          if (f.search) params['search'] = f.search;
          if (f.agence) params['agence'] = f.agence;
          if (f.statut) params['statut'] = f.statut;

          return api.getAll(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                chauffeurs:   Array.isArray(res) ? res : (res.results ?? []),
                loadingState: 'loaded',
                pagination:   { ...store.pagination(), total: res.count },
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.error?.detail ?? 'Erreur chargement chauffeurs.',
              }),
            })
          );
        })
      )
    ),

    loadPermisExpirant: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getPermisExpirant().pipe(
            tapResponse({
              next: (data) => patchState(store, { permisExpirant: data }),
              error: () => {},
            })
          )
        )
      )
    ),

    setFilter(key: keyof ChauffeursState['filters'], value: string): void {
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

