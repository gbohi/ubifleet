// UbiFleet — Alertes SignalStore (NgRx Signals Store Angular 18)
// Ce store est injecté dans le MainLayout (topbar) ET dans le Dashboard
import { inject, computed } from '@angular/core';
import {
  patchState, signalStore,
  withComputed, withMethods, withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { AlerteApiService } from '../../core/services/api.service';
import { Alerte, PrioriteAlerte } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

interface AlertesState {
  alertes:      Alerte[];
  resume:       { total: number; critiques: number; hautes: number; normales: number } | null;
  loadingState: LoadingState;
  error:        string | null;
  pagination:   PaginationState;
  filters: {
    statut:      string;
    priorite:    string;
    type_alerte: string;
    agence:      string;
  };
}

const initialState: AlertesState = {
  alertes:      [],
  resume:       null,
  loadingState: 'idle',
  error:        null,
  pagination:   initialPagination,
  filters: {
    statut:      'active',  // Par défaut : alertes actives
    priorite:    '',
    type_alerte: '',
    agence:      '',
  },
};

export const AlertesStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    isLoading:      computed(() => store.loadingState() === 'loading'),
    isLoaded:       computed(() => store.loadingState() === 'loaded'),
    hasError:       computed(() => store.loadingState() === 'error'),
    totalActives:   computed(() => store.resume()?.total    ?? 0),
    nbCritiques:    computed(() => store.resume()?.critiques ?? 0),
    nbHautes:       computed(() => store.resume()?.hautes    ?? 0),
    // Badge topbar = critiques + hautes
    badgeCount:     computed(() =>
      (store.resume()?.critiques ?? 0) + (store.resume()?.hautes ?? 0)
    ),
    alertesCritiques: computed(() =>
      store.alertes().filter(a => a.priorite === 'critique')
    ),
    alertesParPriorite: computed(() => {
      const order: PrioriteAlerte[] = ['critique', 'haute', 'normale', 'basse'];
      return [...store.alertes()].sort(
        (a, b) => order.indexOf(a.priorite) - order.indexOf(b.priorite)
      );
    }),
  })),

  withMethods((store) => {
    const api = inject(AlerteApiService);
    return {

    // Charger les alertes (liste)
    loadAlertes: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loadingState: 'loading', error: null })),
        switchMap(() => {
          const f = store.filters();
          const p = store.pagination();
          const params: Record<string, any> = { page: p.page, page_size: p.pageSize };
          if (f.statut)      params['statut']      = f.statut;
          if (f.priorite)    params['priorite']    = f.priorite;
          if (f.type_alerte) params['type_alerte'] = f.type_alerte;
          if (f.agence)      params['agence']      = f.agence;

          return api.getAll(params).pipe(
            tapResponse({
              next: (res) => patchState(store, {
                alertes:      Array.isArray(res) ? res : (res.results ?? []),
                loadingState: 'loaded',
                pagination:   { ...store.pagination(), total: res.count },
              }),
              error: (err: any) => patchState(store, {
                loadingState: 'error',
                error: err?.error?.detail ?? 'Erreur chargement alertes.',
              }),
            })
          );
        })
      )
    ),

    // Charger le résumé (pour topbar badge)
    loadResume: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.getResume().pipe(
            tapResponse({
              next: (resume) => patchState(store, { resume }),
              error: () => {},
            })
          )
        )
      )
    ),

    // Traiter une alerte
    traiterAlerte: rxMethod<{ id: string; notes?: string }>(
      pipe(
        switchMap(({ id, notes }) =>
          api.traiter(id, notes).pipe(
            tapResponse({
              next: () => {
                // Retirer l'alerte de la liste active localement
                patchState(store, {
                  alertes: store.alertes().filter(a => a.id !== id),
                  resume: store.resume()
                    ? { ...store.resume()!, total: Math.max(0, store.resume()!.total - 1) }
                    : null,
                });
              },
              error: (err: any) => patchState(store, {
                error: err?.error?.detail ?? 'Erreur traitement alerte.',
              }),
            })
          )
        )
      )
    ),

    // Ignorer une alerte
    ignorerAlerte: rxMethod<string>(
      pipe(
        switchMap((id) =>
          api.ignorer(id).pipe(
            tapResponse({
              next: () => {
                patchState(store, {
                  alertes: store.alertes().filter(a => a.id !== id),
                });
              },
              error: () => {},
            })
          )
        )
      )
    ),

    // Tout marquer comme lu
    marquerToutesLues: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.marquerToutesLues().pipe(
            tapResponse({
              next: () => {
                patchState(store, {
                  alertes: store.alertes().map(a => ({ ...a, statut: 'lue' as const })),
                  resume: store.resume()
                    ? { ...store.resume()!, total: 0, critiques: 0, hautes: 0, normales: 0 }
                    : null,
                });
              },
              error: () => {},
            })
          )
        )
      )
    ),

    genererAlertes: rxMethod<void>(
      pipe(
        switchMap(() =>
          api.generer().pipe(
            tapResponse({
              next: () => {},
              error: () => {},
            })
          )
        )
      )
    ),

    setFilter(key: keyof AlertesState['filters'], value: string): void {
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

