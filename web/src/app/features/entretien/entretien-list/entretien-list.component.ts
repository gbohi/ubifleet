// UbiFleet — Entretien List Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { EntretienStore } from '../../../store/entretien/entretien.store';
import { AgenceApiService } from '../../../core/services/api.service';
import { Agence, Intervention, StatutIntervention, PrioriteIntervention } from '../../../core/models';

@Component({
  selector: 'ubi-entretien-list',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './entretien-list.component.html',
  styleUrls: ['./entretien-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EntretienListComponent implements OnInit {
  store      = inject(EntretienStore);
  private router    = inject(Router);
  private agenceApi = inject(AgenceApiService);

  agences  = signal<Agence[]>([]);
  activeTab = signal<'liste' | 'planifiees' | 'pneus'>('liste');

  // Règle 1 : getters pour les calculs — jamais de filter/map dans le template
  get nbUrgentes(): number {
    return this.store.interventions()
      .filter(i => i.priorite === 'critique' && i.statut === 'planifie')
      .length;
  }

  get nbEnCours(): number {
    return this.store.interventions()
      .filter(i => i.statut === 'en_cours')
      .length;
  }

  get nbTerminees(): number {
    return this.store.interventions()
      .filter(i => i.statut === 'termine')
      .length;
  }

  get coutTotalEstime(): number {
    return this.store.interventions()
      .reduce((acc, i) => acc + Number(i.cout_estime), 0);
  }

  get nbPneusAChanger(): number {
    return this.store.pneusAChanger().length;
  }

  // Chips filtre statut
  readonly statutChips: { label: string; value: string }[] = [
    { label: 'Tous',           value: '' },
    { label: 'Planifiés',      value: 'planifie' },
    { label: 'En cours',       value: 'en_cours' },
    { label: 'Terminés',       value: 'termine' },
    { label: 'Attente pièces', value: 'attente_piece' },
  ];

  readonly prioriteChips: { label: string; value: string }[] = [
    { label: 'Toutes',    value: '' },
    { label: 'Critique',  value: 'critique' },
    { label: 'Haute',     value: 'haute' },
    { label: 'Normale',   value: 'normale' },
  ];

  ngOnInit(): void {
    this.store.loadInterventions();
    this.store.loadPlanifiees();
    this.store.loadPneusAChanger();
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });
  }

  onSearch(event: Event): void {
    this.store.setFilter('search', (event.target as HTMLInputElement).value);
    this.store.loadInterventions();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.store.loadInterventions();
  }

  onStatutFilter(value: string): void {
    this.store.setFilter('statut', value);
    this.store.loadInterventions();
  }

  onPrioriteFilter(value: string): void {
    this.store.setFilter('priorite', value);
    this.store.loadInterventions();
  }

  resetFilters(): void {
    this.store.resetFilters();
    this.store.loadInterventions();
  }

  goToDetail(id: string): void {
    this.router.navigate(['/entretien', id]);
  }

  goToNew(): void {
    this.router.navigate(['/entretien', 'nouveau']);
  }

  onPageChange(page: number): void {
    this.store.setPage(page);
    this.store.loadInterventions();
  }

  get totalPages(): number {
    const p = this.store.pagination();
    return Math.ceil(p.total / p.pageSize) || 1;
  }

  get pages(): number[] {
    const total   = this.totalPages;
    const current = this.store.pagination().page;
    const range: number[] = [];
    for (let i = Math.max(1, current - 2); i <= Math.min(total, current + 2); i++) {
      range.push(i);
    }
    return range;
  }

  // Helpers badges — aucune logique dans le template
  statutBadgeClass(statut: StatutIntervention): string {
    const map: Record<StatutIntervention, string> = {
      planifie:      'badge-navy',
      en_cours:      'badge-info',
      termine:       'badge-green',
      annule:        'badge-gray',
      attente_piece: 'badge-warning',
    };
    return map[statut] ?? 'badge-gray';
  }

  prioriteBadgeClass(priorite: PrioriteIntervention): string {
    const map: Record<PrioriteIntervention, string> = {
      critique: 'badge-danger',
      haute:    'badge-warning',
      normale:  'badge-info',
      basse:    'badge-gray',
    };
    return map[priorite] ?? 'badge-gray';
  }

  usurePctClass(pct: number | null): string {
    if (pct === null) return '';
    if (pct >= 90) return 'danger';
    if (pct >= 70) return 'warning';
    return 'green';
  }

  trackById(_: number, item: Intervention): string { return item.id; }
}
