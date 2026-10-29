// UbiFleet — App Routes
import { Routes } from '@angular/router';
import { authGuard, publicGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  // Auth (public)
  {
    path: 'auth',
    canActivate: [publicGuard],
    loadChildren: () =>
      import('./features/auth/auth.routes').then(m => m.AUTH_ROUTES)
  },

  // App (protégé)
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./layout/main-layout/main-layout.component').then(m => m.MainLayoutComponent),
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
        title: 'Tableau de bord — UbiFleet'
      },
      {
        path: 'vehicules',
        loadChildren: () =>
          import('./features/vehicules/vehicules.routes').then(m => m.VEHICULES_ROUTES),
        title: 'Véhicules — UbiFleet'
      },
  {
    path: 'releves-km',
    loadComponent: () =>
      import('./features/vehicules/releves-km-global/releves-km-global.component')
        .then(m => m.RelevesKmGlobalComponent)
  },
      {
        path: 'carburant',
        loadChildren: () =>
          import('./features/carburant/carburant.routes').then(m => m.CARBURANT_ROUTES),
        title: 'Carburant — UbiFleet'
      },
      {
        path: 'etat-parc',
        loadComponent: () =>
          import('./features/etat-parc/etat-parc.component').then(m => m.EtatParcComponent),
        title: 'État du Parc — UbiFleet'
      },
      {
        path: 'entretien',
        loadChildren: () =>
          import('./features/entretien/entretien.routes').then(m => m.ENTRETIEN_ROUTES),
        title: 'Entretien — UbiFleet'
      },
      {
        path: 'sinistres',
        loadChildren: () =>
          import('./features/sinistres/sinistres.routes').then(m => m.SINISTRES_ROUTES),
        title: 'Sinistres — UbiFleet'
      },
      {
        path: 'grand-livre',
        loadComponent: () =>
          import('./features/grand-livre/grand-livre.component').then(m => m.GrandLivreComponent),
        title: 'Grand Livre — UbiFleet'
      },
      {
        path: 'budget',
        loadChildren: () =>
          import('./features/budget/budget.routes').then(m => m.BUDGET_ROUTES),
        title: 'Budget — UbiFleet'
      },
      {
        path: 'chauffeurs',
        loadChildren: () =>
          import('./features/chauffeurs/chauffeurs.routes').then(m => m.CHAUFFEURS_ROUTES),
        title: 'Chauffeurs — UbiFleet'
      },
      {
        path: 'alertes',
        loadComponent: () =>
          import('./features/alertes/alertes.component').then(m => m.AlertesComponent),
        title: 'Alertes — UbiFleet'
      },
      {
        path: 'rapports',
        loadComponent: () =>
          import('./features/rapports/rapports.component').then(m => m.RapportsComponent),
        title: 'Rapports — UbiFleet'
      },
      {
        path: 'parametres',
        loadComponent: () =>
          import('./features/parametres/parametres.component').then(m => m.ParametresComponent),
        title: 'Paramètres — UbiFleet'
      },
      {
        path: 'controle',
          loadComponent: () =>
            import('./features/controle/controle.component').then(m => m.ControleComponent),
        },
        {
          path: 'controle/:id',
          loadComponent: () =>
            import('./features/controle/controle-detail/controle-detail.component').then(m => m.ControleDetailComponent),
        },
        {
          path: 'vehicules/:id/fiche',
          loadComponent: () =>
            import('./features/vehicules/vehicule-fiche/vehicule-fiche.component').then(m => m.VehiculeFicheComponent),
        },
        {
          path: 'restitution-mensuelle',
          loadComponent: () =>
            import('./features/carburant/restitution-mensuelle/restitution-mensuelle.component')
              .then(m => m.RestitutionMensuelleComponent),
          title: 'Restitution Mensuelle — UbiFleet'
        },
        {
          path: 'demandes',
          loadComponent: () =>
            import('./features/demandes/demandes.component').then(m => m.DemandesComponent),
        },
        {
          path: 'admin/roles',
        loadComponent: () =>
          import('./features/admin/roles/roles.component').then(m => m.RolesComponent),
        title: 'Rôles — UbiFleet'
      },
      {
        path: 'admin/users',
        loadComponent: () =>
          import('./features/admin/users/users.component').then(m => m.UsersComponent),
        title: 'Utilisateurs — UbiFleet'
      },
      {
        path: 'admin/permissions',
        loadComponent: () =>
          import('./features/admin/permissions/permissions.component')
            .then(m => m.PermissionsComponent),
        title: 'Permissions — UbiFleet'
      },
      {
        path: 'profil',
        loadComponent: () =>
          import('./features/profil/profil.component').then(m => m.ProfilComponent),
        title: 'Mon Profil — UbiFleet'
      },
    ]
  },

  // Fallback
  { path: '**', redirectTo: 'dashboard' }
];
