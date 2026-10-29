import { Routes } from '@angular/router';

export const SINISTRES_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./sinistres-list/sinistres-list.component').then(m => m.SinistresListComponent)
  },
  {
    path: 'nouveau',
    loadComponent: () =>
      import('./sinistre-form/sinistre-form.component').then(m => m.SinistreFormComponent)
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./sinistre-detail/sinistre-detail.component').then(m => m.SinistreDetailComponent)
  },
  {
    path: ':id/modifier',
    loadComponent: () =>
      import('./sinistre-form/sinistre-form.component').then(m => m.SinistreFormComponent)
  },
];
