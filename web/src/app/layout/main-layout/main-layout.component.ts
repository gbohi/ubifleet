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
        { label: 'Véhicules',                icon: 'fas fa-car',          route: '/vehicules'  },
        { label: 'Relevés Km',               icon: 'fas fa-tachometer-alt', route: '/releves-km' },
        { label: 'Carburant',                icon: 'fas fa-gas-pump',     route: '/carburant'  },
        { label: 'Restitution Mensuelle',    icon: 'fas fa-file-alt',     route: '/restitution-mensuelle' },
        { label: 'Transactions Total',       icon: 'fas fa-receipt',      route: '/carburant/total' },
        { label: 'Entretiens & Réparations', icon: 'fas fa-wrench',       route: '/entretien'  },
        { label: 'État du Parc',             icon: 'fas fa-clipboard-list', route: '/etat-parc' },
      ]
    },
    {
      label: 'Gestion',
      items: [
        { label: 'Sinistres & Assurances',   icon: 'fas fa-shield-alt',   route: '/sinistres'  },
        { label: 'Budget & Comptabilité',    icon: 'fas fa-coins',        route: '/budget'     },
        { label: 'Grand Livre',              icon: 'fas fa-book',         route: '/grand-livre' },
        { label: 'Chauffeurs',               icon: 'fas fa-id-badge',     route: '/chauffeurs' },
      ]
    },
    {
      label: 'Rapports',
      items: [
        { label: 'Demandes',                 icon: 'fas fa-file-alt',         route: '/demandes' },
        { label: 'Contrôle Véhicule',         icon: 'fas fa-clipboard-check',  route: '/controle' },
        { label: 'Rapports & Stats',         icon: 'fas fa-chart-line',   route: '/rapports'   },
        { label: 'Alertes',                  icon: 'fas fa-bell',         route: '/alertes',
          showBadge: 'alertes', badgeType: 'danger' },
      ]
    },
    {
      label: 'Administration',
      items: [
        { label: 'Utilisateurs',  icon: 'fas fa-users-cog',    route: '/admin/users' },
        { label: 'Rôles',          icon: 'fas fa-user-tag',    route: '/admin/roles' },
        { label: 'Permissions',    icon: 'fas fa-shield-alt',   route: '/admin/permissions' },
        { label: 'Paramètres',               icon: 'fas fa-cog',          route: '/parametres' },
      ]
    }
  ];

  ngOnInit(): void {
    // Charger le résumé des alertes au démarrage (badge topbar)
    this.alertesStore.genererAlertes();
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
