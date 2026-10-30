// UbiFleet — Relevés Kilométrage Global (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { VehiculeApiService, AgenceApiService, ChauffeurApiService } from '../../../core/services/api.service';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { ReleveFormComponent } from '../../../shared/releve-form/releve-form.component';
import { HistoriqueCorrectionsComponent } from '../../../shared/corrections/historique-corrections.component';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';
import { ConsommationFactureeComponent } from '../../carburant/analyses/consommation-facturee.component';
import { ReleveKilometrage, TypeMouvement } from '../../../core/models';

type Tab = 'releves' | 'consommation';

@Component({
  selector: 'ubi-releves-km-global',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, HistoriqueCorrectionsComponent, SuppressionMotifComponent, ReleveFormComponent, ConsommationFactureeComponent],
  templateUrl: './releves-km-global.component.html',
  styleUrls: ['./releves-km-global.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RelevesKmGlobalComponent implements OnInit {
  private vehiculeApi  = inject(VehiculeApiService);
  private agenceApi    = inject(AgenceApiService);
  private chauffeurApi = inject(ChauffeurApiService);

  // Onglets
  activeTab = signal<Tab>('releves');

  // Données relevés
  releves    = signal<ReleveKilometrage[]>([]);
  total      = signal(0);
  page       = signal(1);
  loading    = signal(true);
  chauffeurs = signal<{ id: string; nom_complet: string }[]>([]);
  agences    = signal<{ id: string; nom: string }[]>([]);

  // Filtres
  searchImmat    = signal('');
  filterType     = signal('');
  filterChauffeur= signal('');
  filterDateDe   = signal('');
  filterDateA    = signal('');
  filterKmMin    = signal('');
  filterKmMax    = signal('');

  // Types de mouvement paramétrables (Paramètres › Types de mouvement)
  typesMvt = inject(TypesMouvementService);

  get totalPages(): number { return Math.ceil(this.total() / 20) || 1; }
  get pages(): number[] {
    const cur = this.page(), max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.typesMvt.charger();
    this.loadReleves();
    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res) => this.chauffeurs.set(
        (res.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });
    this.agenceApi.getAll().subscribe({
      next: (res: any) => this.agences.set(res.results ?? res ?? []),
      error: () => {},
    });
  }

  loadReleves(): void {
    this.loading.set(true);
    const filters: Record<string, any> = { page: this.page(), page_size: 20 };
    if (this.searchImmat())     filters['search']         = this.searchImmat();
    if (this.filterType())      filters['type_mouvement'] = this.filterType();
    if (this.filterChauffeur()) filters['chauffeur']      = this.filterChauffeur();
    if (this.filterDateDe())    filters['date_releve__gte']= this.filterDateDe();
    if (this.filterDateA())     filters['date_releve__lte']= this.filterDateA();
    if (this.filterKmMin())     filters['kilometrage__gte']= this.filterKmMin();
    if (this.filterKmMax())     filters['kilometrage__lte']= this.filterKmMax();

    this.vehiculeApi.getRelevesKm(filters).subscribe({
      next: (res) => {
        this.releves.set(res.results ?? []);
        this.total.set(res.count ?? 0);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onSearch(event: Event): void {
    this.searchImmat.set((event.target as HTMLInputElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  onType(event: Event): void {
    this.filterType.set((event.target as HTMLSelectElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  onChauffeur(event: Event): void {
    this.filterChauffeur.set((event.target as HTMLSelectElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  onDateDe(event: Event): void {
    this.filterDateDe.set((event.target as HTMLInputElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  onDateA(event: Event): void {
    this.filterDateA.set((event.target as HTMLInputElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  onKmMin(event: Event): void {
    this.filterKmMin.set((event.target as HTMLInputElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  onKmMax(event: Event): void {
    this.filterKmMax.set((event.target as HTMLInputElement).value);
    this.page.set(1);
    this.loadReleves();
  }

  resetFilters(): void {
    this.searchImmat.set('');
    this.filterType.set('');
    this.filterChauffeur.set('');
    this.filterDateDe.set('');
    this.filterDateA.set('');
    this.filterKmMin.set('');
    this.filterKmMax.set('');
    this.page.set(1);
    this.loadReleves();
  }

  get hasFilters(): boolean {
    return !!(this.searchImmat() || this.filterType() || this.filterChauffeur() ||
              this.filterDateDe() || this.filterDateA() || this.filterKmMin() || this.filterKmMax());
  }

  onPageChange(p: number): void { this.page.set(p); this.loadReleves(); }

  typeMouvementClass(type: TypeMouvement): string {
    return this.typesMvt.classeBadge(type);
  }

  // ── Formulaire de relevé (commun à toute l'application) ──────────
  /** Formulaire ouvert ; `releveEdite` : relevé corrigé (null = nouveau relevé). */
  formOuvert  = signal(false);
  releveEdite = signal<ReleveKilometrage | null>(null);

  ouvrirNouveauReleve(): void { this.ouvrirForm(null); }

  ouvrirForm(r: ReleveKilometrage | null): void {
    this.releveEdite.set(r);
    this.formOuvert.set(true);
  }

  apresEnregistrement(): void {
    this.formOuvert.set(false);
    if (!this.releveEdite()) this.page.set(1);
    this.loadReleves();
  }

  // ── Corrections : suppression (motif obligatoire hors délai) et historique ──
  releveASupprimer = signal<ReleveKilometrage | null>(null);
  deleteEnCours    = signal(false);
  deleteErreur     = signal('');
  historiqueDe     = signal<ReleveKilometrage | null>(null);

  supprimerReleve(motif: string): void {
    const r = this.releveASupprimer();
    if (!r || this.deleteEnCours()) return;
    this.deleteEnCours.set(true);
    this.deleteErreur.set('');
    this.vehiculeApi.deleteReleveKm(r.id, motif || undefined).subscribe({
      next: () => { this.deleteEnCours.set(false); this.releveASupprimer.set(null); this.loadReleves(); },
      error: (err) => {
        this.deleteEnCours.set(false);
        this.deleteErreur.set(messageErreurApi(err, 'Suppression impossible.'));
      },
    });
  }
  // ── Export CSV de tous les relevés de la base ────────────────────
  relevesExportLoading = signal(false);

  exportRelevesCsv(): void {
    if (this.relevesExportLoading()) return;
    this.relevesExportLoading.set(true);
    this.vehiculeApi.getRelevesKm({ page_size: 100000 }).subscribe({
      next: (res) => {
        this.relevesExportLoading.set(false);
        const rows = res.results ?? [];
        if (!rows.length) return;
        const sep = ';'; const eol = '\r\n';
        const hdrs = ['Date','Immatriculation','Véhicule','Kilométrage','Type',
                      'Chauffeur','Tournée','Notes','Saisi par','Créé le'].join(sep);
        const data = rows.map((r: any) => [
          r.date_releve, r.vehicule_immat, r.vehicule_designation ?? '',
          r.kilometrage, r.type_display ?? r.type_mouvement,
          r.chauffeur_nom ?? '', r.tournee_code ? r.tournee_code + ' — ' + r.tournee_libelle : '',
          (r.notes ?? '').replace(/[\r\n;]+/g, ' '),
          r.created_by_nom ?? '', r.created_at?.split('T')[0] ?? '',
        ].join(sep)).join(eol);
        const csv = '\uFEFF' + hdrs + eol + data;
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `releves_km_${new Date().toISOString().split('T')[0]}.csv`;
        a.click(); URL.revokeObjectURL(a.href);
      },
      error: () => this.relevesExportLoading.set(false),
    });
  }

  // ── Lightbox photo tableau de bord ───────────────────────────────
  photoLightbox = signal<string | null>(null);

  ouvrirPhoto(e: Event, url: string): void {
    e.stopPropagation();
    this.photoLightbox.set(url);
  }
  fermerPhoto(): void { this.photoLightbox.set(null); }

  // ── Popup détail d'un relevé ─────────────────────────────────────
  detailReleve = signal<ReleveKilometrage | null>(null);

  ouvrirDetail(r: ReleveKilometrage): void { this.detailReleve.set(r); }
  fermerDetail(): void                     { this.detailReleve.set(null); }
}
