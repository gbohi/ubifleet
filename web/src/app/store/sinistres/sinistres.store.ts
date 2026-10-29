// UbiFleet — Sinistres SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { SinistreApiService } from '../../core/services/api.service';
import { Sinistre, ContratAssurance } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

interface SinistresState {
  sinistres:         Sinistre[];
  contratsExpirant:  ContratAssurance[];
  contratsExpires:   ContratAssurance[];
  stats:             any | null;
  loadingState:      LoadingState;
  error:             string | null;
  pagination:        PaginationState;
  filters: {
    search:       string;
    agence:       string;
    type_sinistre: string;
    statut:       string;
  };
}

const initialState: SinistresState = {
  sinistres:        [],
  contratsExpirant: [],
  contratsExpires:  [],
  stats:            null,
  loadingState:     'idle',
  error:            null,
  pagination:       initialPagination,
  filters: { search: '', agence: '', type_sinistre: '', statut: '' },
};

export const SinistresStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:       computed(() => store.loadingState() === 'loading'),
    isLoaded:        computed(() => store.loadingState() === 'loaded'),
    hasError:        computed(() => store.loadingState() === 'error'),
    nbEnCours:       computed(() =>
      store.sinistres().filter(s =>
        ['declare', 'en_instruction', 'expertise', 'reparation'].includes(s.statut)
      ).length
    ),
    nbContratsUrgents: computed(() =>
      store.contratsExpirant().filter(c => c.jours_restants <= 7).length
    ),
  })),

  withMethods((store) => {
    const api = inject(SinistreApiService);
    return {

    loadSinistres: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const f = store.filters();
          const p = store.pagination();
          const params: Record<string, any> = { page: p.page, page_size: p.pageSize };
          if (f.search)        params['search']        = f.search;
          if (f.agence)        params['agence']        = f.agence;
          if (f.type_sinistre) params['type_sinistre'] = f.type_sinistre;
          if (f.statut)        params['statut']        = f.statut;

          return api.getSinistres(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                sinistres:    Array.isArray(res) ? res : (res.results ?? []),
                loadingState: 'loaded',
                pagination:   { ...store.pagination(), total: res.count },
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.error?.detail ?? 'Erreur chargement sinistres.',
              }),
            })
          );
        })
      )
    ),

    loadContratsExpirant: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getContratsExpirant().pipe(
            tapResponse({
              next: (data) => patchState(store, { contratsExpirant: data }),
              error: () => {},
            })
          )
        )
      )
    ),

    loadContratsExpires: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getContratsExpires().pipe(
            tapResponse({
              next: (data) => patchState(store, { contratsExpires: data }),
              error: () => {},
            })
          )
        )
      )
    ),

    setFilter(key: keyof SinistresState['filters'], value: string): void {
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

