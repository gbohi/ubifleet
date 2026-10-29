import { Routes } from '@angular/router';
export const VEHICULES_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./vehicules-list/vehicules-list.component').then(m => m.VehiculesListComponent)
  },
  {
    path: 'nouveau',
    loadComponent: () =>
      import('./vehicule-form/vehicule-form.component').then(m => m.VehiculeFormComponent)
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./vehicule-detail/vehicule-detail.component').then(m => m.VehiculeDetailComponent)
  },
  {
    path: ':id/modifier',
    loadComponent: () =>
      import('./vehicule-form/vehicule-form.component').then(m => m.VehiculeFormComponent)
  },
  {
    path: ':id/releves-km',
    loadComponent: () =>
      import('./vehicule-releves-km/vehicule-releves-km.component')
        .then(m => m.VehiculeRelevesKmComponent)
  },
];
