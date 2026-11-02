// UbiFleet — Chauffeurs List Component (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { ChauffeursStore } from '../../../store/chauffeurs/chauffeurs.store';
import { AgenceApiService, ChauffeurApiService } from '../../../core/services/api.service';
import { Agence, Chauffeur } from '../../../core/models';

@Component({
  selector: 'ubi-chauffeurs-list',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './chauffeurs-list.component.html',
  styleUrls: ['./chauffeurs-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChauffeursListComponent implements OnInit {
  store        = inject(ChauffeursStore);
  private router       = inject(Router);
  private agenceApi    = inject(AgenceApiService);
  private chauffeurApi = inject(ChauffeurApiService);

  agences       = signal<Agence[]>([]);
  viewMode      = signal<'cards' | 'table'>('cards');
  deleteConfirm = signal<string | null>(null);

  statutChips = [
    { label: 'En poste',  value: 'en_poste' },
    { label: 'Actifs',    value: 'actif' },
    { label: 'En congé',  value: 'conge' },
    { label: 'Absents',   value: 'absent' },
    { label: 'Suspendus', value: 'suspendu' },
    { label: 'Départs',   value: 'depart' },
    { label: 'Tous',      value: '' },
  ];

  /** Totaux de tout l'effectif (agence et recherche appliquées), pas de la seule page affichée. */
  stats = signal<any | null>(null);
  archiveErreur = signal('');
  private chargerStats(): void {
    const f = this.store.filters();
    const params: Record<string, any> = {};
    if (f.search) params['search'] = f.search;
    if (f.agence) params['agence'] = f.agence;
    this.chauffeurApi.getStats(params).subscribe({ next: s => this.stats.set(s), error: () => {} });
  }
  private recharger(): void { this.store.loadChauffeurs(); this.chargerStats(); }

  ngOnInit(): void {
    this.recharger();
    this.store.loadPermisExpirant();
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });
  }

  onSearch(event: Event): void {
    this.store.setFilter('search', (event.target as HTMLInputElement).value);
    this.recharger();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.recharger();
  }

  onStatutFilter(statut: string): void {
    this.store.setFilter('statut', statut);
    this.store.loadChauffeurs();
  }

  resetFilters(): void {
    this.store.setFilter('search', '');
    this.store.setFilter('agence', '');
    this.store.setFilter('statut', 'en_poste');
    this.recharger();
  }

  goToDetail(id: string): void  { this.router.navigate(['/chauffeurs', id]); }
  goToEdit(event: Event, id: string): void {
    event.stopPropagation();
    this.router.navigate(['/chauffeurs', id, 'modifier']);
  }
  goToNew(): void { this.router.navigate(['/chauffeurs', 'nouveau']); }

  confirmDelete(event: Event, id: string): void {
    event.stopPropagation();
    this.deleteConfirm.set(id);
  }
  cancelDelete(): void  { this.deleteConfirm.set(null); }
  doDelete(id: string): void {
    this.archiveErreur.set('');
    this.chauffeurApi.archiver(id).subscribe({
      next: () => { this.deleteConfirm.set(null); this.recharger(); },
      error: err => this.archiveErreur.set(err?.error?.detail ?? 'Archivage impossible.'),
    });
  }

  onPageChange(page: number): void {
    this.store.setPage(page);
    this.store.loadChauffeurs();
  }

  get totalPages(): number {
    const p = this.store.pagination();
    return Math.ceil(p.total / p.pageSize) || 1;
  }

  get pages(): number[] {
    const total = this.totalPages;
    const cur   = this.store.pagination().page;
    const range: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(total, cur + 2); i++) range.push(i);
    return range;
  }

  permisUrgenceClass(c: Chauffeur): string {
    if (c.permis_expire) return 'danger';
    const j = c.jours_expiration_permis;
    if (j !== null && j <= 30) return 'danger';
    if (j !== null && j <= 60) return 'warning';
    return 'ok';
  }

  statutBadgeClass(statut: string): string {
    const map: Record<string, string> = {
      actif: 'badge-green', conge: 'badge-info',
      absent: 'badge-warning', suspendu: 'badge-danger', depart: 'badge-gray',
    };
    return map[statut] ?? 'badge-gray';
  }

  trackById(_: number, c: Chauffeur): string { return c.id; }
}
