// UbiFleet — Vehicules SignalStore (NgRx Signals Store Angular 18)
import { inject, computed } from '@angular/core';
import {
  patchState,
  signalStore,
  withComputed,
  withMethods,
  withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { pipe, switchMap, tap } from 'rxjs';
import { VehiculeApiService } from '../../core/services/api.service';
import { Vehicule, VehiculeDetail } from '../../core/models';
import { LoadingState, PaginationState, initialPagination } from '../store.utils';

// ── État du store ──
interface VehiculesState {
  vehicules:        Vehicule[];
  selectedVehicule: VehiculeDetail | null;
  loadingState:     LoadingState;
  detailLoading:    boolean;
  error:            string | null;
  pagination:       PaginationState;
  filters: {
    search:         string;
    agence:         string;
    statut:         string;
    type_carburant: string;
    type_vehicule:  string;
  };
  stats: any | null;
}

const initialState: VehiculesState = {
  vehicules:        [],
  selectedVehicule: null,
  loadingState:     'idle',
  detailLoading:    false,
  error:            null,
  pagination:       initialPagination,
  filters: {
    search:         '',
    agence:         '',
    statut:         '',
    type_carburant: '',
    type_vehicule:  '',
  },
  stats: null,
};

// ── SignalStore ──
export const VehiculesStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  // ── Computed (selectors) ──
  withComputed((store) => ({
    isLoading: computed(() => store.loadingState() === 'loading'),
    isLoaded:  computed(() => store.loadingState() === 'loaded'),
    hasError:  computed(() => store.loadingState() === 'error'),

    totalVehicules: computed(() => store.pagination().total),

    vehiculesEnService: computed(() =>
      store.vehicules().filter(v => v.statut_couleur === 'green')
    ),
    vehiculesEnRevision: computed(() =>
      store.vehicules().filter(v => v.statut_couleur === 'orange')
    ),
    vehiculesImmobilises: computed(() =>
      store.vehicules().filter(v => v.statut_couleur === 'red')
    ),
    vehiculesRevisionDue: computed(() =>
      store.vehicules().filter(v => v.revision_due)
    ),
    hasActiveFilters: computed(() => {
      const f = store.filters();
      return !!(f.search || f.agence || f.statut || f.type_carburant || f.type_vehicule);
    }),
  })),

  // ── Methods (actions + effects) ──
  withMethods((store) => {
    // Injection des services à l'intérieur de withMethods
    // pour que TypeScript infère correctement les types
    const api = inject(VehiculeApiService);

    return {

      // Charger la liste des véhicules
      loadVehicules: rxMethod<void>(
        pipe(
          tap(() => patchState(store, { loadingState: 'loading', error: null })),
          switchMap(() => {
            const f = store.filters();
            const p = store.pagination();
            const params: Record<string, any> = {
              page:      p.page,
              page_size: p.pageSize,
            };
            if (f.search)         params['search']         = f.search;
            if (f.agence)         params['agence']         = f.agence;
            if (f.statut)         params['statut']         = f.statut;
            if (f.type_carburant) params['type_carburant'] = f.type_carburant;
            if (f.type_vehicule)  params['type_vehicule']  = f.type_vehicule;

            return api.getAll(params).pipe(
              tapResponse({
                next: (res) => patchState(store, {
                  vehicules:    Array.isArray(res) ? res : (res.results ?? []),
                  loadingState: 'loaded',
                  pagination:   { ...store.pagination(), total: res.count ?? 0 },
                }),
                error: (err: any) => patchState(store, {
                  loadingState: 'error',
                  error: err?.status === 0
                    ? 'Serveur inaccessible. Vérifiez que le backend Django est démarré.'
                    : err?.error?.detail ?? 'Erreur lors du chargement des véhicules.',
                }),
              })
            );
          })
        )
      ),

      // Charger le détail d'un véhicule
      loadVehiculeDetail: rxMethod<string>(
        pipe(
          tap(() => patchState(store, { detailLoading: true, selectedVehicule: null, error: null })),
          switchMap((id: string) =>
            api.getById(id).pipe(
              tapResponse({
                next: (v) => patchState(store, {
                  selectedVehicule: v,
                  detailLoading:    false,
                }),
                error: (err: any) => patchState(store, {
                  detailLoading: false,
                  error: err?.status === 0
                    ? 'Serveur inaccessible.'
                    : err?.error?.detail ?? 'Véhicule introuvable.',
                }),
              })
            )
          )
        )
      ),

      // Charger les statistiques du parc
      loadStats: rxMethod<void>(
        pipe(
          switchMap(() =>
            api.getStats().pipe(
              tapResponse({
                next:  (stats) => patchState(store, { stats }),
                error: ()      => { /* silencieux */ },
              })
            )
          )
        )
      ),

      // Mettre à jour le kilométrage
      updateKilometrage: rxMethod<{ id: string; kilometrage: number; date_releve: string }>(
        pipe(
          switchMap((data) =>
            api.updateKilometrage(data.id, {
              kilometrage:  data.kilometrage,
              date_releve:  data.date_releve,
            }).pipe(
              tapResponse({
                next: () => {
                  const updated = store.vehicules().map(v =>
                    v.id === data.id
                      ? { ...v, kilometrage_actuel: data.kilometrage }
                      : v
                  );
                  patchState(store, { vehicules: updated });
                },
                error: (err: any) => patchState(store, {
                  error: err?.error?.detail ?? 'Erreur mise à jour kilométrage.',
                }),
              })
            )
          )
        )
      ),

      // ── Actions synchrones ──

      setFilter(key: keyof VehiculesState['filters'], value: string): void {
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
        patchState(store, {
          pagination: { ...store.pagination(), page },
        });
      },

      setSelectedVehicule(vehicule: VehiculeDetail | null): void {
        patchState(store, { selectedVehicule: vehicule });
      },

      removeVehicule(id: string): void {
        patchState(store, {
          vehicules: store.vehicules().filter(v => v.id !== id),
          pagination: {
            ...store.pagination(),
            total: Math.max(0, store.pagination().total - 1),
          },
        });
      },

      clearError(): void {
        patchState(store, { error: null });
      },

    };
  })
);
