import { Routes } from '@angular/router';
import { accesGuard } from '../../core/guards/acces.guard';

export const CARBURANT_ROUTES: Routes = [
  {
    path: '',
    canActivate: [accesGuard],
    data: { acces: 'carburant' },
    loadComponent: () =>
      import('./carburant-list/carburant-list.component')
        .then(m => m.CarburantListComponent)
  },
  {
    path: 'nouveau',
    canActivate: [accesGuard],
    data: { acces: 'carburant' },
    loadComponent: () =>
      import('./plein-form/plein-form.component')
        .then(m => m.PleinFormComponent)
  },
  {
    path: ':id/modifier',
    canActivate: [accesGuard],
    data: { acces: 'carburant' },
    loadComponent: () =>
      import('./plein-form/plein-form.component')
        .then(m => m.PleinFormComponent)
  },
  {
    path: 'total',
    canActivate: [accesGuard],
    data: { acces: 'transactions_total' },
    loadComponent: () =>
      import('./total-import/total-import.component')
        .then(m => m.TotalImportComponent),
    title: 'Transactions Total — UbiFleet'
  },
];
