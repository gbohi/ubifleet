// UbiFleet — App Routes
import { Routes } from '@angular/router';
import { authGuard, publicGuard } from './core/guards/auth.guard';
import { accesGuard } from './core/guards/acces.guard';

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
        canActivate: [accesGuard],
        data: { acces: 'vehicules' },
        loadChildren: () =>
          import('./features/vehicules/vehicules.routes').then(m => m.VEHICULES_ROUTES),
        title: 'Véhicules — UbiFleet'
      },
  {
    path: 'releves-km',
    canActivate: [accesGuard],
    data: { acces: 'releves_km' },
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
        canActivate: [accesGuard],
        data: { acces: 'etat_parc' },
        loadComponent: () =>
          import('./features/etat-parc/etat-parc.component').then(m => m.EtatParcComponent),
        title: 'État du Parc — UbiFleet'
      },
      {
        path: 'entretien',
        canActivate: [accesGuard],
        data: { acces: 'entretien' },
        loadChildren: () =>
          import('./features/entretien/entretien.routes').then(m => m.ENTRETIEN_ROUTES),
        title: 'Entretien — UbiFleet'
      },
      {
        path: 'sinistres',
        canActivate: [accesGuard],
        data: { acces: 'sinistres' },
        loadChildren: () =>
          import('./features/sinistres/sinistres.routes').then(m => m.SINISTRES_ROUTES),
        title: 'Sinistres — UbiFleet'
      },
      {
        path: 'grand-livre',
        canActivate: [accesGuard],
        data: { acces: 'grand_livre' },
        loadComponent: () =>
          import('./features/grand-livre/grand-livre.component').then(m => m.GrandLivreComponent),
        title: 'Grand Livre — UbiFleet'
      },
      {
        path: 'budget',
        canActivate: [accesGuard],
        data: { acces: 'budget' },
        loadChildren: () =>
          import('./features/budget/budget.routes').then(m => m.BUDGET_ROUTES),
        title: 'Budget — UbiFleet'
      },
      {
        path: 'chauffeurs',
        canActivate: [accesGuard],
        data: { acces: 'chauffeurs' },
        loadChildren: () =>
          import('./features/chauffeurs/chauffeurs.routes').then(m => m.CHAUFFEURS_ROUTES),
        title: 'Chauffeurs — UbiFleet'
      },
      {
        path: 'alertes',
        canActivate: [accesGuard],
        data: { acces: 'alertes' },
        loadComponent: () =>
          import('./features/alertes/alertes.component').then(m => m.AlertesComponent),
        title: 'Alertes — UbiFleet'
      },
      {
        path: 'rapports',
        canActivate: [accesGuard],
        data: { acces: 'rapports' },
        loadComponent: () =>
          import('./features/rapports/rapports.component').then(m => m.RapportsComponent),
        title: 'Rapports — UbiFleet'
      },
      {
        path: 'parametres',
        canActivate: [accesGuard],
        data: { acces: 'parametres' },
        loadComponent: () =>
          import('./features/parametres/parametres.component').then(m => m.ParametresComponent),
        title: 'Paramètres — UbiFleet'
      },
      {
        path: 'controle',
        canActivate: [accesGuard],
        data: { acces: 'controle' },
          loadComponent: () =>
            import('./features/controle/controle.component').then(m => m.ControleComponent),
        },
        {
          path: 'controle/:id',
          canActivate: [accesGuard],
          data: { acces: 'controle' },
          loadComponent: () =>
            import('./features/controle/controle-detail/controle-detail.component').then(m => m.ControleDetailComponent),
        },
        {
          path: 'vehicules/:id/fiche',
          canActivate: [accesGuard],
          data: { acces: 'vehicules' },
          loadComponent: () =>
            import('./features/vehicules/vehicule-fiche/vehicule-fiche.component').then(m => m.VehiculeFicheComponent),
        },
        {
          path: 'restitution-mensuelle',
          canActivate: [accesGuard],
          data: { acces: 'restitution_mensuelle' },
          loadComponent: () =>
            import('./features/carburant/restitution-mensuelle/restitution-mensuelle.component')
              .then(m => m.RestitutionMensuelleComponent),
          title: 'Restitution Mensuelle — UbiFleet'
        },
        {
          path: 'demandes',
          canActivate: [accesGuard],
          data: { acces: 'demandes' },
          loadComponent: () =>
            import('./features/demandes/demandes.component').then(m => m.DemandesComponent),
        },
        {
          path: 'admin/roles',
          canActivate: [accesGuard],
          data: { acces: 'roles' },
        loadComponent: () =>
          import('./features/admin/roles/roles.component').then(m => m.RolesComponent),
        title: 'Rôles — UbiFleet'
      },
      {
        path: 'admin/users',
        canActivate: [accesGuard],
        data: { acces: 'utilisateurs' },
        loadComponent: () =>
          import('./features/admin/users/users.component').then(m => m.UsersComponent),
        title: 'Utilisateurs — UbiFleet'
      },
      {
        path: 'admin/permissions',
        canActivate: [accesGuard],
        data: { acces: 'permissions' },
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
