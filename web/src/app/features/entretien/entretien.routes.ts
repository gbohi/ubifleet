import { Routes } from '@angular/router';

export const ENTRETIEN_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./entretien-list/entretien-list.component')
        .then(m => m.EntretienListComponent)
  },
  {
    path: 'nouveau',
    loadComponent: () =>
      import('./intervention-form/intervention-form.component')
        .then(m => m.InterventionFormComponent)
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./intervention-detail/intervention-detail.component')
        .then(m => m.InterventionDetailComponent)
  },
  {
    path: ':id/modifier',
    loadComponent: () =>
      import('./intervention-form/intervention-form.component')
        .then(m => m.InterventionFormComponent)
  },
];
