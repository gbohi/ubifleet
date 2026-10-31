// UbiFleet — Carburant List Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit, ChangeDetectionStrategy, signal,
} from '@angular/core';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { DecimalPipe, DatePipe } from '@angular/common';
import { CarburantStore } from '../../../store/carburant/carburant.store';
import { AgenceApiService, CarburantApiService } from '../../../core/services/api.service';
import { Agence, PleinCarburant } from '../../../core/models';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { SuiviTourneesComponent } from '../suivi-tournees/suivi-tournees.component';
import { ConsommationVehiculesComponent } from '../analyses/consommation-vehicules.component';
import { ClassementChauffeursComponent } from '../analyses/classement-chauffeurs.component';
import { EvolutionAgencesComponent } from '../analyses/evolution-agences.component';
import { RapprochementTotalComponent } from '../analyses/rapprochement-total.component';
import { OptionVehicule, OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';

type CarburantTab = 'pleins' | 'anomalies' | 'suivi' | 'consommation' | 'chauffeurs' | 'evolution' | 'rapprochement';

@Component({
  selector: 'ubi-carburant-list',
  standalone: true,
  imports: [RouterLink, DecimalPipe, DatePipe, SuppressionMotifComponent, SuiviTourneesComponent,
            ConsommationVehiculesComponent, ClassementChauffeursComponent, EvolutionAgencesComponent, RapprochementTotalComponent, SelectRechercheComponent],
  templateUrl: './carburant-list.component.html',
  styleUrls: ['./carburant-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CarburantListComponent implements OnInit {

  store = inject(CarburantStore);
  private router       = inject(Router);
  private route        = inject(ActivatedRoute);
  private agenceApi    = inject(AgenceApiService);
  private carburantApi = inject(CarburantApiService);
  private options      = inject(OptionsSaisieService);
  readonly typesMvt    = inject(TypesMouvementService);

  /** Listes avec recherche des filtres (véhicules et chauffeurs de la base). */
  vehiculesFiltre  = signal<OptionVehicule[]>([]);
  chauffeursFiltre = signal<OptionRecherche[]>([]);

  agences      = signal<Agence[]>([]);
  activeTab    = signal<CarburantTab>('pleins');
  /** Prise de carburant à supprimer (fenêtre de confirmation avec motif). */
  deleteConfirm = signal<PleinCarburant | null>(null);
  deleteEnCours = signal(false);
  deleteErreur  = signal('');


  // Getters — jamais de filter dans le template
  get totalVolumeFormatted(): string {
    const v = this.store.totalVolumeL();
    return v >= 1000 ? `${(v / 1000).toFixed(1)} kL` : `${v.toFixed(0)} L`;
  }

  get totalMontantFormatted(): string {
    const m = this.store.totalMontantFCFA();
    if (m >= 1_000_000) return `${(m / 1_000_000).toFixed(1)}M FCFA`;
    if (m >= 1_000)     return `${(m / 1_000).toFixed(0)} K FCFA`;
    return `${m} FCFA`;
  }

  ngOnInit(): void {
    // Lire le queryParam vehicule (depuis vehicule-detail)
    this.route.queryParams.subscribe(params => {
      if (params['vehicule']) {
        this.store.setFilter('vehicule', params['vehicule']);
      }
    });

    this.store.loadPleins();
    this.store.loadAnomalies();
    this.store.loadStats({});

    this.typesMvt.charger();
    this.options.vehicules().subscribe({ next: l => this.vehiculesFiltre.set(l), error: () => {} });
    this.options.chauffeurs(true).subscribe({ next: l => this.chauffeursFiltre.set(l), error: () => {} });

    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });
  }

  onSearch(event: Event): void {
    this.store.setFilter('search', (event.target as HTMLInputElement).value);
    this.store.loadPleins();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.store.loadPleins();
  }

  onFiltreListe(cle: 'vehicule' | 'chauffeur' | 'type_mouvement' | 'date_min' | 'date_max', valeur: string | null): void {
    this.store.setFilter(cle, valeur ?? '');
    this.store.loadPleins();
  }

  resetFilters(): void {
    this.store.resetFilters();
    this.store.loadPleins();
  }

  goToNew(): void { this.router.navigate(['/carburant', 'nouveau']); }
  goToEdit(event: Event, id: string): void {
    event.stopPropagation();
    this.router.navigate(['/carburant', id, 'modifier']);
  }

  confirmDelete(event: Event, plein: PleinCarburant): void {
    event.stopPropagation();
    this.deleteErreur.set('');
    this.deleteConfirm.set(plein);
  }

  cancelDelete(): void { this.deleteConfirm.set(null); }

  doDelete(motif: string): void {
    const plein = this.deleteConfirm();
    if (!plein || this.deleteEnCours()) return;
    this.deleteEnCours.set(true);
    this.carburantApi.deletePlein(plein.id, motif || undefined).subscribe({
      next: () => {
        this.deleteEnCours.set(false);
        this.deleteConfirm.set(null);
        this.store.loadPleins();
        this.store.loadStats({});
      },
      error: (err) => {
        this.deleteEnCours.set(false);
        this.deleteErreur.set(messageErreurApi(err, 'Suppression impossible.'));
      },
    });
  }

  onPageChange(page: number): void {
    this.store.setPage(page);
    this.store.loadPleins();
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

  // ── Photo tableau de bord lightbox ──
  photoLightbox = signal<string | null>(null);

  openPhoto(e: Event, url: string): void {
    e.stopPropagation();
    this.photoLightbox.set(url);
  }
  closePhoto(): void { this.photoLightbox.set(null); }

  trackById(_: number, p: PleinCarburant): string { return p.id; }
}
