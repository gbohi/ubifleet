// UbiFleet — Vehicules List Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { VehiculesStore } from '../../../store/vehicules/vehicules.store';
import { AgenceApiService, VehiculeApiService, ParametrageApiService } from '../../../core/services/api.service';
import { Agence, Vehicule, StatutVehicule } from '../../../core/models';

@Component({
  selector: 'ubi-vehicules-list',
  standalone: true,
  imports: [RouterLink, DecimalPipe],
  templateUrl: './vehicules-list.component.html',
  styleUrls: ['./vehicules-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculesListComponent implements OnInit {
  store        = inject(VehiculesStore);
  private router      = inject(Router);
  private agenceApi      = inject(AgenceApiService);
  private parametrageApi = inject(ParametrageApiService);
  private vehiculeApi = inject(VehiculeApiService);

  agences       = signal<Agence[]>([]);
  viewMode      = signal<'cards' | 'table'>('cards');
  deleteConfirm = signal<string | null>(null);

  statutsDisponibles = signal<any[]>([]);

  typesVehicule = [
    { label: 'Tous types',  value: '' },
    { label: 'Berline',     value: 'berline' },
    { label: 'SUV / 4×4',  value: 'suv' },
    { label: 'Minibus',     value: 'minibus' },
    { label: 'Camionnette', value: 'camionnette' },
    { label: 'Pick-up',     value: 'pickup' },
    { label: 'Camion',      value: 'camion' },
    { label: 'Moto',        value: 'moto' },
  ];

  typesCarburant = [
    { label: 'Tous',       value: '' },
    { label: 'Diesel',     value: 'diesel' },
    { label: 'Essence',    value: 'essence' },
    { label: 'Hybride',    value: 'hybride' },
    { label: 'Électrique', value: 'electrique' },
    { label: 'GPL',        value: 'gpl' },
  ];

  /** Affectations / usages (référentiel paramétrable). */
  affectations = signal<any[]>([]);

  ngOnInit(): void {
    this.parametrageApi.getStatutsVehicule().subscribe({
      next: (l) => this.statutsDisponibles.set(l.filter((s: any) => s.actif)),
      error: () => {},
    });
    this.parametrageApi.getAffectations().subscribe({
      next: (l) => this.affectations.set(l.filter((a: any) => a.actif)),
      error: () => {},
    });
    this.store.loadVehicules();
    this.store.loadStats();
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });
  }

  onSearch(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.store.setFilter('search', val);
    this.rafraichir();
  }

  onStatutFilter(statut: string): void {
    this.store.setFilter('statut', statut);
    this.store.loadVehicules();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.rafraichir();
  }

  onTypeFilter(event: Event): void {
    this.store.setFilter('type_vehicule', (event.target as HTMLSelectElement).value);
    this.rafraichir();
  }

  onCarburantFilter(event: Event): void {
    this.store.setFilter('type_carburant', (event.target as HTMLSelectElement).value);
    this.rafraichir();
  }

  onAffectationFilter(valeur: string): void {
    this.store.setFilter('affectation', valeur);
    this.rafraichir();
  }

  onRevisionDue(): void {
    this.store.setFilter('revision_due', this.store.filters().revision_due ? '' : 'true');
    this.store.loadVehicules();
  }

  resetFilters(): void {
    this.store.resetFilters();
    this.rafraichir();
  }

  /** Liste et statistiques (les statistiques suivent les filtres, sauf le statut). */
  private rafraichir(): void {
    this.store.loadVehicules();
    this.store.loadStats();
  }

  couleurPastille(couleur: string): string {
    return ({ green: 'green', orange: 'orange', red: 'red', blue: 'blue' } as Record<string, string>)[couleur] ?? 'gray';
  }

  goToDetail(id: string): void {
    this.router.navigate(['/vehicules', id]);
  }

  goToEdit(event: Event, id: string): void {
    event.stopPropagation();
    this.router.navigate(['/vehicules', id, 'modifier']);
  }

  goToNew(): void {
    this.router.navigate(['/vehicules', 'nouveau']);
  }

  confirmDelete(event: Event, id: string): void {
    event.stopPropagation();
    this.deleteConfirm.set(id);
  }

  cancelDelete(): void {
    this.deleteConfirm.set(null);
  }

  deleteErreur = signal('');

  doDelete(id: string): void {
    this.deleteErreur.set('');
    this.vehiculeApi.delete(id).subscribe({
      next: () => { this.store.removeVehicule(id); this.deleteConfirm.set(null); },
      error: (err) => this.deleteErreur.set(err?.error?.detail ?? "L'archivage a échoué."),
    });
  }

  onPageChange(page: number): void {
    this.store.setPage(page);
    this.store.loadVehicules();
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

  statutBadgeClass(couleur: string): string {
    const map: Record<string, string> = {
      green: 'badge-green', orange: 'badge-warning',
      red: 'badge-danger', blue: 'badge-blue', gray: 'badge-gray',
    };
    return map[couleur] ?? 'badge-gray';
  }

  statutDotClass(couleur: string): string {
    const map: Record<string, string> = {
      green: 'green', orange: 'orange',
      red: 'red', blue: 'blue', gray: 'gray',
    };
    return map[couleur] ?? 'gray';
  }

  trackById(_: number, v: Vehicule): string { return v.id; }

  exportLoading = signal(false);

  exportExcel(): void {
    if (this.exportLoading()) return;
    this.exportLoading.set(true);
    // Tous les véhicules, par pages de 1000 (taille maximale acceptée par le serveur)
    const lignes: Vehicule[] = [];
    const page = (n: number) => this.vehiculeApi.getAll({ page: n, page_size: 1000 }).subscribe({
      next: (res: any) => {
        lignes.push(...(res.results ?? []));
        if (res.next) { page(n + 1); return; }
        this.exportLoading.set(false);
        if (lignes.length) this.genererCsv(lignes);
      },
      error: () => this.exportLoading.set(false),
    });
    page(1);
  }

  private genererCsv(rows: Vehicule[]): void {
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Immatriculation','Marque','Modèle','Année','Type','Carburant',
                  'Statut','Agence','Km actuel','Km révision','Conso référence L/100','Carte carburant','Mise en service'].join(sep);
    const data = rows.map((v: Vehicule) => [
      v.immatriculation,
      v.marque_libelle ?? '',
      v.modele_libelle ?? '',
      v.annee,
      v.type_vehicule,
      v.type_carburant ?? '',
      v.statut_display ?? v.statut ?? '',
      v.agence_detail?.nom ?? '',
      v.kilometrage_actuel ?? 0,
      v.kilometrage_revision ?? '',
      v.conso_theorique_origine ?? '',
      v.numero_carte_carburant ?? '',
      v.date_mise_en_service ?? '',
    ].join(sep)).join(eol);
    const csv = '\uFEFF' + hdrs + eol + data;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `vehicules_${new Date().toISOString().split('T')[0]}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
  }
}
