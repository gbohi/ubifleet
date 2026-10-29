import { Routes } from '@angular/router';

export const CARBURANT_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./carburant-list/carburant-list.component')
        .then(m => m.CarburantListComponent)
  },
  {
    path: 'nouveau',
    loadComponent: () =>
      import('./plein-form/plein-form.component')
        .then(m => m.PleinFormComponent)
  },
  {
    path: ':id/modifier',
    loadComponent: () =>
      import('./plein-form/plein-form.component')
        .then(m => m.PleinFormComponent)
  },
  {
    path: 'total',
    loadComponent: () =>
      import('./total-import/total-import.component')
        .then(m => m.TotalImportComponent),
    title: 'Transactions Total — UbiFleet'
  },
];
