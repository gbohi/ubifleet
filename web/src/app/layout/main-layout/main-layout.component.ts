// UbiFleet — Main Layout (Angular 18 + NgRx Signals Store)
import {
  Component, inject, signal, computed,
  OnInit, ChangeDetectionStrategy
} from '@angular/core';
import { RouterOutlet, RouterLink, Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { AuthService } from '../../core/services/auth.service';
import { AlertesStore } from '../../store/alertes/alertes.store';

export interface NavItem {
  label:      string;
  icon:       string;
  route:      string;
  acces?:     string;      // Clé de /auth/me/acces/ ; absent = toujours visible
  badgeType?: 'default' | 'danger';
  showBadge?: 'alertes';   // Badge dynamique depuis le store
  staticBadge?: number;    // Badge statique
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

@Component({
  selector: 'ubi-main-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  templateUrl: './main-layout.component.html',
  styleUrls: ['./main-layout.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MainLayoutComponent implements OnInit {
  private auth   = inject(AuthService);
  private router = inject(Router);
  alertesStore   = inject(AlertesStore);

  sidebarOpen = signal(true);
  user        = computed(() => this.auth.currentUser());
  currentUrl  = signal(this.router.url);

  // Badge dynamique des alertes depuis le SignalStore
  alertesBadge = computed(() => this.alertesStore.badgeCount());

  navSections: NavSection[] = [
    {
      label: 'Principal',
      items: [
        { label: 'Tableau de bord',          icon: 'fas fa-chart-pie',   route: '/dashboard'  },
        { label: 'Véhicules',                icon: 'fas fa-car',          route: '/vehicules', acces: 'vehicules'  },
        { label: 'Relevés Km',               icon: 'fas fa-tachometer-alt', route: '/releves-km', acces: 'releves_km' },
        { label: 'Carburant',                icon: 'fas fa-gas-pump',     route: '/carburant', acces: 'carburant'  },
        { label: 'Restitution Mensuelle',    icon: 'fas fa-file-alt',     route: '/restitution-mensuelle', acces: 'restitution_mensuelle' },
        { label: 'Transactions Total',       icon: 'fas fa-receipt',      route: '/carburant/total', acces: 'transactions_total' },
        { label: 'Entretiens & Réparations', icon: 'fas fa-wrench',       route: '/entretien', acces: 'entretien'  },
        { label: 'État du Parc',             icon: 'fas fa-clipboard-list', route: '/etat-parc', acces: 'etat_parc' },
      ]
    },
    {
      label: 'Gestion',
      items: [
        { label: 'Sinistres & Assurances',   icon: 'fas fa-shield-alt',   route: '/sinistres', acces: 'sinistres'  },
        { label: 'Budget & Comptabilité',    icon: 'fas fa-coins',        route: '/budget', acces: 'budget'     },
        { label: 'Grand Livre',              icon: 'fas fa-book',         route: '/grand-livre', acces: 'grand_livre' },
        { label: 'Chauffeurs',               icon: 'fas fa-id-badge',     route: '/chauffeurs', acces: 'chauffeurs' },
      ]
    },
    {
      label: 'Rapports',
      items: [
        { label: 'Demandes',                 icon: 'fas fa-file-alt',         route: '/demandes', acces: 'demandes' },
        { label: 'Contrôle Véhicule',         icon: 'fas fa-clipboard-check',  route: '/controle', acces: 'controle' },
        { label: 'Rapports & Stats',         icon: 'fas fa-chart-line',   route: '/rapports', acces: 'rapports'   },
        { label: 'Alertes',                  icon: 'fas fa-bell',         route: '/alertes', acces: 'alertes',
          showBadge: 'alertes', badgeType: 'danger' },
      ]
    },
    {
      label: 'Administration',
      items: [
        { label: 'Utilisateurs',  icon: 'fas fa-users-cog',    route: '/admin/users', acces: 'utilisateurs' },
        { label: 'Rôles',          icon: 'fas fa-user-tag',    route: '/admin/roles', acces: 'roles' },
        { label: 'Permissions',    icon: 'fas fa-shield-alt',   route: '/admin/permissions', acces: 'permissions' },
        { label: 'Paramètres',               icon: 'fas fa-cog',          route: '/parametres', acces: 'parametres' },
      ]
    }
  ];

  // Menu filtré selon les droits de l'utilisateur ; sections vides masquées
  visibleSections = computed(() =>
    this.navSections
      .map(s => ({ ...s, items: s.items.filter(i => !i.acces || this.auth.peutAcceder(i.acces)) }))
      .filter(s => s.items.length > 0)
  );

  ngOnInit(): void {
    // Profil et droits à jour (rôle ou agence modifiés depuis la connexion)
    this.auth.rafraichirSession();

    // Charger le résumé des alertes au démarrage (badge topbar).
    // La génération globale est réservée aux profils autorisés.
    if (this.auth.peutAcceder('alertes_generer') && this.auth.acces()) {
      this.alertesStore.genererAlertes();
    }
    this.alertesStore.loadResume();

    // Suivre l'URL active pour un surlignage précis du menu
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(e => this.currentUrl.set(e.urlAfterRedirects));
  }

  // Toutes les routes du menu, utilisées pour déterminer la correspondance
  // la plus précise (préfixe le plus long) — évite que /carburant reste actif
  // quand on est sur /carburant/total, qui est un lien distinct.
  private allNavRoutes = computed(() =>
    this.navSections.flatMap(s => s.items.map(i => i.route))
  );

  isNavActive(route: string): boolean {
    const url = this.currentUrl().split('?')[0];
    if (route === '/dashboard') return url === '/dashboard';

    if (url !== route && !url.startsWith(route + '/')) return false;

    // Trouver la route du menu la plus longue qui correspond à l'URL actuelle
    const bestMatch = this.allNavRoutes()
      .filter(r => url === r || url.startsWith(r + '/'))
      .sort((a, b) => b.length - a.length)[0];

    return bestMatch === route;
  }

  getBadge(item: NavItem): number {
    if (item.showBadge === 'alertes') return this.alertesBadge();
    return item.staticBadge ?? 0;
  }

  toggleSidebar(): void {
    this.sidebarOpen.update(v => !v);
  }

  logout(): void {
    this.auth.logout();
  }

  get userInitials(): string {
    const u = this.user();
    if (!u) return 'U';
    const initials = `${u.first_name?.[0] ?? ''}${u.last_name?.[0] ?? ''}`.toUpperCase();
    return initials || u.email[0].toUpperCase();
  }
}
