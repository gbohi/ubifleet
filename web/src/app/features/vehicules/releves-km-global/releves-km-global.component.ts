// UbiFleet — Relevés Kilométrage Global (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { forkJoin } from 'rxjs';
import { VehiculeApiService, AgenceApiService, ChauffeurApiService, TotalImportApiService } from '../../../core/services/api.service';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { ReleveFormComponent } from '../../../shared/releve-form/releve-form.component';
import { HistoriqueCorrectionsComponent } from '../../../shared/corrections/historique-corrections.component';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';
import { ReleveKilometrage, TypeMouvement } from '../../../core/models';

type Tab = 'releves' | 'consommation';

interface ConsoKmRow {
  immatriculation: string;
  marque: string; modele: string;
  km_debut: number; km_fin: number; distance: number;
  volume_total: number; nb_transactions: number;
  conso_100: number | null;        // Conso via relevés km × Total
  conso_total: number | null;      // Conso directe Total (km_prec / km_actuel)
  volume_total_direct: number;     // Volume Total pour la conso directe
  km_total_debut: number | null;   // Km début issu de Total
  km_total_fin: number | null;     // Km fin issu de Total
  source_volume: string;
}

@Component({
  selector: 'ubi-releves-km-global',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, HistoriqueCorrectionsComponent, SuppressionMotifComponent, ReleveFormComponent],
  templateUrl: './releves-km-global.component.html',
  styleUrls: ['./releves-km-global.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RelevesKmGlobalComponent implements OnInit {
  private vehiculeApi  = inject(VehiculeApiService);
  private agenceApi    = inject(AgenceApiService);
  private chauffeurApi = inject(ChauffeurApiService);
  private totalApi     = inject(TotalImportApiService);

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

  // ── Onglet Consommation L/100 ────────────────────────────────────
  consoDateDebut = signal('');
  consoDateFin   = signal('');
  consoVehicule  = signal('');
  consoAgence    = signal('');
  consoLoading   = signal(false);
  consoError     = signal('');
  consoData      = signal<ConsoKmRow[]>([]);
  consoSortKey   = signal('conso_100');
  consoSortAsc   = signal(false);

  consoSorted = computed(() => {
    const key = this.consoSortKey();
    const asc = this.consoSortAsc();
    return [...this.consoData()].sort((a, b) => {
      let va: number;
      let vb: number;
      if (key === 'distance_total') {
        va = (a.km_total_fin && a.km_total_debut) ? a.km_total_fin - a.km_total_debut : 0;
        vb = (b.km_total_fin && b.km_total_debut) ? b.km_total_fin - b.km_total_debut : 0;
      } else {
        va = (a[key as keyof ConsoKmRow] ?? 0) as number;
        vb = (b[key as keyof ConsoKmRow] ?? 0) as number;
      }
      return asc ? va - vb : vb - va;
    });
  });

  onConsoInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement | HTMLSelectElement).value;
    if (field === 'debut')    this.consoDateDebut.set(val);
    if (field === 'fin')      this.consoDateFin.set(val);
    if (field === 'vehicule') this.consoVehicule.set(val);
    if (field === 'agence')   this.consoAgence.set(val);
  }

  calculerConso(): void {
    if (!this.consoDateDebut() || !this.consoDateFin()) {
      this.consoError.set('Veuillez renseigner les deux dates.'); return;
    }
    this.consoLoading.set(true); this.consoError.set('');
    const params: Record<string, any> = {
      date_debut: this.consoDateDebut(),
      date_fin:   this.consoDateFin(),
    };
    if (this.consoVehicule()) params['vehicule'] = this.consoVehicule();
    if (this.consoAgence())   params['agence']   = this.consoAgence();

    // Appels parallèles : relevés km × Total  ET  consommation directe Total
    forkJoin({
      releves: this.vehiculeApi.getConsommationKm(params),
      total:   this.totalApi.getConsommation({
        date_debut: this.consoDateDebut(),
        date_fin:   this.consoDateFin(),
      }),
    }).subscribe({
      next: ({ releves, total }) => {
        // Indexer les résultats Total par immatriculation
        const totalMap: Record<string, any> = {};
        for (const t of (total.resultats ?? [])) {
          totalMap[(t.immatriculation ?? '').toUpperCase().trim()] = t;
        }

        const rows: ConsoKmRow[] = (releves.resultats ?? []).map((r: any) => {
          const immat = (r.immatriculation ?? '').toUpperCase().trim();
          const t = totalMap[immat];
          return {
            ...r,
            conso_total:        t?.conso_100 ?? null,
            volume_total_direct: t?.volume_total ?? 0,
            km_total_debut:     t?.km_debut ?? null,
            km_total_fin:       t?.km_fin ?? null,
          };
        });

        // Ajouter les véhicules présents dans Total mais absents des relevés
        const relevesImmats = new Set(
          (releves.resultats ?? []).map((r: any) =>
            (r.immatriculation ?? '').toUpperCase().trim()
          )
        );
        for (const t of (total.resultats ?? [])) {
          const immat = (t.immatriculation ?? '').toUpperCase().trim();
          if (!relevesImmats.has(immat)) {
            rows.push({
              immatriculation:     t.immatriculation,
              marque: '', modele: '',
              km_debut: 0, km_fin: 0, distance: 0,
              volume_total: 0, nb_transactions: 0,
              conso_100:           null,
              conso_total:         t.conso_100 ?? null,
              volume_total_direct: t.volume_total ?? 0,
              km_total_debut:      t.km_debut ?? null,
              km_total_fin:        t.km_fin ?? null,
              source_volume:       'total_only',
            });
          }
        }

        this.consoData.set(rows);
        this.consoLoading.set(false);
      },
      error: (err) => {
        this.consoError.set(err?.error?.detail ?? 'Erreur de calcul.');
        this.consoLoading.set(false);
      },
    });
  }

  sortConso(key: string): void {
    if (this.consoSortKey() === key) this.consoSortAsc.set(!this.consoSortAsc());
    else { this.consoSortKey.set(key); this.consoSortAsc.set(false); }
  }

  consoBadge(v: number | null): string {
    if (v === null) return 'badge-gray';
    if (v <= 8)  return 'badge-green';
    if (v <= 12) return 'badge-warning';
    return 'badge-danger';
  }

  exportConsoCsv(): void {
    const rows = this.consoSorted();
    if (!rows.length) return;
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Immatriculation','Marque','Modèle',
                  'Km début (Relevés)','Km fin (Relevés)','Distance (km)',
                  'Volume Total (L)','Nb transactions',
                  'Conso Relevés×Total (L/100)','Conso Directe Total (L/100)',
                  'Km début Total','Km fin Total'].join(sep);
    const data = rows.map(r => [
      r.immatriculation, r.marque, r.modele,
      r.km_debut || '', r.km_fin || '', r.distance || '',
      r.volume_total, r.nb_transactions,
      r.conso_100 ?? 'N/A', r.conso_total ?? 'N/A',
      r.km_total_debut ?? '', r.km_total_fin ?? '',
    ].join(sep)).join(eol);
    const csv = '\uFEFF' + hdrs + eol + data;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `conso_km_${this.consoDateDebut()}_${this.consoDateFin()}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
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
