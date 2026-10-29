import { Routes } from '@angular/router';

export const CHAUFFEURS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./chauffeurs-list/chauffeurs-list.component').then(m => m.ChauffeursListComponent)
  },
  {
    path: 'nouveau',
    loadComponent: () =>
      import('./chauffeur-form/chauffeur-form.component').then(m => m.ChauffeurFormComponent)
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./chauffeur-detail/chauffeur-detail.component').then(m => m.ChauffeurDetailComponent)
  },
  {
    path: ':id/modifier',
    loadComponent: () =>
      import('./chauffeur-form/chauffeur-form.component').then(m => m.ChauffeurFormComponent)
  },
];
