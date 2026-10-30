// UbiFleet — Carburant List Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, computed,
  ElementRef, ViewChild
} from '@angular/core';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { DecimalPipe, DatePipe } from '@angular/common';
import { CarburantStore } from '../../../store/carburant/carburant.store';
import { AgenceApiService, VehiculeApiService, CarburantApiService } from '../../../core/services/api.service';
import { Agence, PleinCarburant } from '../../../core/models';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';

interface ConsoVehicule {
  immatriculation: string; marque?: string; modele?: string;
  km_debut: number; km_fin: number; km_parcourus: number;
  volume_total: number; montant_total: number;
  nb_pleins: number; conso_100: number | null;
  premier_date?: string | null; premier_heure?: string | null;
  dernier_date?: string | null; dernier_heure?: string | null;
}
interface AgencePoint { mois: string; volume: number; montant: number; nb: number; }
interface AgenceSerie { nom: string; points: AgencePoint[]; }
interface ComparaisonRow {
  immatriculation: string;
  ubifleet_volume: number | null;
  ubifleet_km: number | null;
  ubifleet_nb_pleins: number | null;
  ubifleet_conso_100: number | null;
  ubifleet_premier_date?: string | null;
  ubifleet_premier_heure?: string | null;
  ubifleet_dernier_date?: string | null;
  ubifleet_dernier_heure?: string | null;
  total_volume: number | null;
  total_km: number | null;
  total_nb_pleins: number | null;
  total_conso_100: number | null;
  total_premier_date?: string | null;
  total_premier_heure?: string | null;
  total_dernier_date?: string | null;
  total_dernier_heure?: string | null;
  ecart_conso: number | null;
  ecart_pct: number | null;
  statut: string;
}

const CHART_COLORS = ['#092440','#5bd988','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16','#f97316','#ec4899'];

type CarburantTab = 'pleins' | 'dotations' | 'anomalies' | 'suivi' | 'consommation' | 'moyenne_periode' | 'evolution' | 'comparaison';

@Component({
  selector: 'ubi-carburant-list',
  standalone: true,
  imports: [RouterLink, DecimalPipe, DatePipe, SuppressionMotifComponent],
  templateUrl: './carburant-list.component.html',
  styleUrls: ['./carburant-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CarburantListComponent implements OnInit, OnDestroy {
  @ViewChild('chartCanvas') chartCanvas?: ElementRef<HTMLCanvasElement>;

  store = inject(CarburantStore);
  private router       = inject(Router);
  private route        = inject(ActivatedRoute);
  private agenceApi    = inject(AgenceApiService);
  private carburantApi = inject(CarburantApiService);

  agences      = signal<Agence[]>([]);
  activeTab    = signal<CarburantTab>('pleins');
  /** Prise de carburant à supprimer (fenêtre de confirmation avec motif). */
  deleteConfirm = signal<PleinCarburant | null>(null);
  deleteEnCours = signal(false);
  deleteErreur  = signal('');

  readonly moisList = [
    { val: '', label: 'Tous les mois' },
    { val: '1', label: 'Janvier' }, { val: '2', label: 'Février' },
    { val: '3', label: 'Mars' }, { val: '4', label: 'Avril' },
    { val: '5', label: 'Mai' }, { val: '6', label: 'Juin' },
    { val: '7', label: 'Juillet' }, { val: '8', label: 'Août' },
    { val: '9', label: 'Septembre' }, { val: '10', label: 'Octobre' },
    { val: '11', label: 'Novembre' }, { val: '12', label: 'Décembre' },
  ];

  readonly anneesList = [
    new Date().getFullYear(),
    new Date().getFullYear() - 1,
    new Date().getFullYear() - 2,
  ].map(a => ({ val: String(a), label: String(a) }));

  // ── Consommation L/100 ──
  consoDateDebut = signal('');
  consoDateFin   = signal('');
  consoImmat     = signal('');
  consoChauf     = signal('');
  consoLoading   = signal(false);
  consoData      = signal<ConsoVehicule[]>([]);
  consoError     = signal('');
  consoSortKey   = signal<string>('conso_100');
  consoSortAsc   = signal(false);

  consoSorted = computed(() => {
    const key = this.consoSortKey() as keyof ConsoVehicule;
    const asc = this.consoSortAsc();
    return [...this.consoData()].sort((a, b) => {
      const va = (a[key] ?? 0) as number;
      const vb = (b[key] ?? 0) as number;
      return asc ? va - vb : vb - va;
    });
  });

  // ── Moyenne période (1er plein ↔ dernier plein de la période) ──
  moyDateDebut = signal('');
  moyDateFin   = signal('');
  moyImmat     = signal('');
  moyChauf     = signal('');
  moyLoading   = signal(false);
  moyData      = signal<ConsoVehicule[]>([]);
  moyError     = signal('');
  moySortKey   = signal<string>('conso_100');
  moySortAsc   = signal(false);

  moySorted = computed(() => {
    const key = this.moySortKey() as keyof ConsoVehicule;
    const asc = this.moySortAsc();
    return [...this.moyData()].sort((a, b) => {
      const va = (a[key] ?? 0) as number;
      const vb = (b[key] ?? 0) as number;
      return asc ? va - vb : vb - va;
    });
  });

  // ── Évolution par agence ──
  evoDateDebut = signal('');
  evoDateFin   = signal('');
  evoImmat     = signal('');
  evoChauf     = signal('');
  evoLoading   = signal(false);
  evoData      = signal<AgenceSerie[]>([]);
  evoError     = signal('');
  evoMetrique  = signal<'volume' | 'montant' | 'nb'>('volume');
  private evoChart: any = null;

  // ── Comparaison UbiFleet vs Total ──
  compDateDebut = signal('');
  compDateFin   = signal('');
  compImmat     = signal('');
  compLoading   = signal(false);
  compError     = signal('');
  compData      = signal<{ stats: any; resultats: ComparaisonRow[] } | null>(null);
  compFiltre    = signal<string>('');

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
    this.store.loadDotations({});
    this.store.loadStats({});

    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });

    const now   = new Date();
    const debut = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    const fmt   = (d: Date) => d.toISOString().split('T')[0];
    this.consoDateDebut.set(fmt(debut)); this.consoDateFin.set(fmt(now));
    this.moyDateDebut.set(fmt(debut));   this.moyDateFin.set(fmt(now));
    this.evoDateDebut.set(fmt(debut));   this.evoDateFin.set(fmt(now));
    this.compDateDebut.set(fmt(debut));  this.compDateFin.set(fmt(now));
  }

  ngOnDestroy(): void {
    if (this.evoChart) { this.evoChart.destroy(); this.evoChart = null; }
  }

  onSearch(event: Event): void {
    this.store.setFilter('search', (event.target as HTMLInputElement).value);
    this.store.loadPleins();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.store.loadPleins();
  }

  onMoisFilter(event: Event): void {
    this.store.setFilter('mois', (event.target as HTMLSelectElement).value);
    this.store.loadPleins();
  }

  onAnneeFilter(event: Event): void {
    this.store.setFilter('annee', (event.target as HTMLSelectElement).value);
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

  // ── Consommation L/100 ──
  onConsoInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut') this.consoDateDebut.set(val);
    if (field === 'fin')   this.consoDateFin.set(val);
    if (field === 'immat') this.consoImmat.set(val);
    if (field === 'chauf') this.consoChauf.set(val);
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
    if (this.consoImmat()) params['immatriculation'] = this.consoImmat();
    if (this.consoChauf()) params['chauffeur']        = this.consoChauf();

    this.carburantApi.getConsommation(params).subscribe({
      next: (res) => { this.consoData.set(res.resultats ?? []); this.consoLoading.set(false); },
      error: (err) => { this.consoError.set(err?.error?.detail ?? 'Erreur de calcul.'); this.consoLoading.set(false); },
    });
  }

  sortConso(key: string): void {
    if (this.consoSortKey() === key) this.consoSortAsc.set(!this.consoSortAsc());
    else { this.consoSortKey.set(key); this.consoSortAsc.set(false); }
  }

  consoClass(v: number | null): string {
    if (v === null) return 'badge-gray';
    if (v <= 8)  return 'badge-green';
    if (v <= 12) return 'badge-warning';
    return 'badge-danger';
  }

  exportConsoCsv(): void {
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Immatriculation','Marque','Modèle','Km début','Km fin','Km parcourus',
                  'Volume (L)','Montant (FCFA)','Nb prises de carburant','Conso L/100km',
                  'Première prise','Heure','Dernière prise','Heure'].join(sep);
    const data = this.consoSorted().map(r =>
      [r.immatriculation, r.marque ?? '', r.modele ?? '', r.km_debut, r.km_fin, r.km_parcourus,
       r.volume_total, r.montant_total, r.nb_pleins, r.conso_100 ?? 'N/A',
       r.premier_date ?? '', r.premier_heure ?? '', r.dernier_date ?? '', r.dernier_heure ?? ''].join(sep)
    ).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data,
      `consommation_carburant_${this.consoDateDebut()}_${this.consoDateFin()}.csv`);
  }

  // ── Moyenne période ──
  onMoyInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut') this.moyDateDebut.set(val);
    if (field === 'fin')   this.moyDateFin.set(val);
    if (field === 'immat') this.moyImmat.set(val);
    if (field === 'chauf') this.moyChauf.set(val);
  }

  calculerMoyennePeriode(): void {
    if (!this.moyDateDebut() || !this.moyDateFin()) {
      this.moyError.set('Veuillez renseigner les deux dates.'); return;
    }
    this.moyLoading.set(true); this.moyError.set('');
    const params: Record<string, any> = {
      date_debut: this.moyDateDebut(),
      date_fin:   this.moyDateFin(),
    };
    if (this.moyImmat()) params['immatriculation'] = this.moyImmat();
    if (this.moyChauf()) params['chauffeur']        = this.moyChauf();

    this.carburantApi.getConsommationMoyennePeriode(params).subscribe({
      next: (res) => { this.moyData.set(res.resultats ?? []); this.moyLoading.set(false); },
      error: (err) => { this.moyError.set(err?.error?.detail ?? 'Erreur de calcul.'); this.moyLoading.set(false); },
    });
  }

  sortMoy(key: string): void {
    if (this.moySortKey() === key) this.moySortAsc.set(!this.moySortAsc());
    else { this.moySortKey.set(key); this.moySortAsc.set(false); }
  }

  moyClass(v: number | null): string {
    if (v === null) return 'badge-gray';
    if (v <= 8)  return 'badge-green';
    if (v <= 12) return 'badge-warning';
    return 'badge-danger';
  }

  exportMoyCsv(): void {
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Immatriculation','Marque','Modèle','Km début','Km fin','Km parcourus',
                  'Volume (L)','Montant (FCFA)','Nb prises de carburant','Conso moyenne L/100km',
                  'Première prise','Heure','Dernière prise','Heure'].join(sep);
    const data = this.moySorted().map(r =>
      [r.immatriculation, r.marque ?? '', r.modele ?? '', r.km_debut, r.km_fin, r.km_parcourus,
       r.volume_total, r.montant_total, r.nb_pleins, r.conso_100 ?? 'N/A',
       r.premier_date ?? '', r.premier_heure ?? '', r.dernier_date ?? '', r.dernier_heure ?? ''].join(sep)
    ).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data,
      `moyenne_periode_carburant_${this.moyDateDebut()}_${this.moyDateFin()}.csv`);
  }

  // ── Évolution par agence ──
  onEvoInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut') this.evoDateDebut.set(val);
    if (field === 'fin')   this.evoDateFin.set(val);
    if (field === 'immat') this.evoImmat.set(val);
    if (field === 'chauf') this.evoChauf.set(val);
  }

  chargerEvolution(): void {
    if (!this.evoDateDebut() || !this.evoDateFin()) {
      this.evoError.set('Veuillez renseigner les deux dates.'); return;
    }
    this.evoLoading.set(true); this.evoError.set('');
    const params: Record<string, any> = {
      date_debut: this.evoDateDebut(),
      date_fin:   this.evoDateFin(),
    };
    if (this.evoImmat()) params['immatriculation'] = this.evoImmat();
    if (this.evoChauf()) params['chauffeur']        = this.evoChauf();

    this.carburantApi.getEvolutionAgences(params).subscribe({
      next: (res) => {
        this.evoData.set(res.agences ?? []);
        this.evoLoading.set(false);
        setTimeout(() => this.renderChart(), 50);
      },
      error: (err) => { this.evoError.set(err?.error?.detail ?? 'Erreur.'); this.evoLoading.set(false); },
    });
  }

  renderChart(): void {
    const canvas = this.chartCanvas?.nativeElement;
    if (!canvas) return;
    const agences  = this.evoData();
    const metrique = this.evoMetrique();
    if (!agences.length) return;

    const allMois = Array.from(new Set(agences.flatMap(a => a.points.map(p => p.mois)))).sort();
    const datasets = agences.map((a, i) => {
      const map = new Map(a.points.map(p => [p.mois, p[metrique]]));
      return {
        label:           a.nom || 'Agence ?',
        data:            allMois.map(m => map.get(m) ?? 0),
        borderColor:     CHART_COLORS[i % CHART_COLORS.length],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '22',
        borderWidth: 2.5, pointRadius: 4, pointHoverRadius: 6,
        tension: 0.35, fill: false,
      };
    });

    const labels: Record<string, string> = { volume: 'Volume (litres)', montant: 'Montant (FCFA)', nb: 'Nb prises de carburant' };
    const Chart = (window as any)['Chart'];
    if (!Chart) { this.loadChartJs(() => this.renderChart()); return; }
    if (this.evoChart) { this.evoChart.destroy(); this.evoChart = null; }

    this.evoChart = new Chart(canvas, {
      type: 'line',
      data: { labels: allMois, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { font: { size: 12 } } },
          tooltip: { callbacks: { label: (ctx: any) => {
            const v = ctx.parsed.y;
            if (metrique === 'volume')  return `${ctx.dataset.label}: ${v.toFixed(2)} L`;
            if (metrique === 'montant') return `${ctx.dataset.label}: ${v.toLocaleString('fr-FR')} FCFA`;
            return `${ctx.dataset.label}: ${v} prise(s) de carburant`;
          }}},
        },
        scales: {
          x: { grid: { color: '#f0f0f0' }, ticks: { font: { size: 11 } } },
          y: { grid: { color: '#f0f0f0' }, title: { display: true, text: labels[metrique], font: { size: 11 } }, ticks: { font: { size: 11 } } },
        },
      },
    });
  }

  loadChartJs(cb: () => void): void {
    if ((window as any)['Chart']) { cb(); return; }
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
    s.onload = cb;
    document.head.appendChild(s);
  }

  onMetriqueChange(m: 'volume' | 'montant' | 'nb'): void {
    this.evoMetrique.set(m);
    if (this.evoData().length > 0) setTimeout(() => this.renderChart(), 10);
  }

  getColor(i: number): string { return CHART_COLORS[i % CHART_COLORS.length]; }

  sumPoints(points: AgencePoint[], key: 'volume' | 'montant' | 'nb'): number {
    return points.reduce((acc, p) => acc + (p[key] || 0), 0);
  }

  private downloadCsv(csv: string, filename: string): void {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click();
    URL.revokeObjectURL(a.href);
  }

  // ── Comparaison UbiFleet vs Total ──
  onCompInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut') this.compDateDebut.set(val);
    if (field === 'fin')   this.compDateFin.set(val);
    if (field === 'immat') this.compImmat.set(val);
  }

  lancerComparaison(): void {
    if (!this.compDateDebut() || !this.compDateFin()) {
      this.compError.set('Veuillez renseigner les deux dates.'); return;
    }
    this.compLoading.set(true); this.compError.set(''); this.compFiltre.set('');
    const params: Record<string, any> = {
      date_debut: this.compDateDebut(),
      date_fin:   this.compDateFin(),
    };
    if (this.compImmat()) params['immatriculation'] = this.compImmat();

    this.carburantApi.getComparaisonTotal(params).subscribe({
      next: (res) => { this.compData.set(res); this.compLoading.set(false); },
      error: (err) => { this.compError.set(err?.error?.detail ?? 'Erreur de comparaison.'); this.compLoading.set(false); },
    });
  }

  compLignes(): ComparaisonRow[] {
    const data = this.compData();
    if (!data) return [];
    const filtre = this.compFiltre();
    return filtre ? data.resultats.filter(r => r.statut === filtre) : data.resultats;
  }

  compStatutClass(statut: string): string {
    const map: Record<string, string> = {
      coherent:               'badge-green',
      ecart_modere:           'badge-warning',
      ecart_important:        'badge-danger',
      ubifleet_absent:        'badge-navy',
      total_absent:           'badge-gray',
      donnees_insuffisantes:  'badge-gray',
    };
    return map[statut] ?? 'badge-gray';
  }

  compStatutLabel(statut: string): string {
    const map: Record<string, string> = {
      coherent:               'Cohérent',
      ecart_modere:           'Écart modéré',
      ecart_important:        'Écart important',
      ubifleet_absent:        'Absent UbiFleet',
      total_absent:           'Absent Total',
      donnees_insuffisantes:  'Données insuff.',
    };
    return map[statut] ?? statut;
  }

  toggleCompFiltre(statut: string): void {
    this.compFiltre.set(this.compFiltre() === statut ? '' : statut);
  }

  exportCompCsv(): void {
    const rows = this.compLignes();
    if (!rows.length) return;
    const sep = ';'; const eol = '\r\n';
    const hdrs = [
      'Statut','Immatriculation',
      'Volume UbiFleet (L)','Km UbiFleet','Nb prises UbiFleet','Conso UbiFleet (L/100)',
      'Première prise UbiFleet','Heure','Dernière prise UbiFleet','Heure',
      'Volume Total (L)','Km Total','Nb prises Total','Conso Total (L/100)',
      'Première transaction Total','Heure','Dernière transaction Total','Heure',
      'Écart conso (L/100)','% Écart'
    ].join(sep);
    const data = rows.map(r => [
      this.compStatutLabel(r.statut), r.immatriculation,
      r.ubifleet_volume ?? '', r.ubifleet_km ?? '', r.ubifleet_nb_pleins ?? '', r.ubifleet_conso_100 ?? '',
      r.ubifleet_premier_date ?? '', r.ubifleet_premier_heure ?? '',
      r.ubifleet_dernier_date ?? '', r.ubifleet_dernier_heure ?? '',
      r.total_volume ?? '', r.total_km ?? '', r.total_nb_pleins ?? '', r.total_conso_100 ?? '',
      r.total_premier_date ?? '', r.total_premier_heure ?? '',
      r.total_dernier_date ?? '', r.total_dernier_heure ?? '',
      r.ecart_conso ?? '', r.ecart_pct ?? '',
    ].join(sep)).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data,
      `comparaison_ubifleet_total_${this.compDateDebut()}_${this.compDateFin()}.csv`);
  }

  // ── Photo tableau de bord lightbox ──
  photoLightbox = signal<string | null>(null);

  openPhoto(e: Event, url: string): void {
    e.stopPropagation();
    this.photoLightbox.set(url);
  }
  closePhoto(): void { this.photoLightbox.set(null); }

  trackById(_: number, p: PleinCarburant): string { return p.id; }

  // ── Onglet Suivi tournées ────────────────────────────────────────
  suiviDateDebut   = signal('');
  suiviDateFin     = signal('');
  suiviAgence      = signal('');
  suiviImmat       = signal('');
  suiviLoading     = signal(false);
  suiviData        = signal<any[]>([]);
  suiviError       = signal('');
  suiviCount       = signal(0);

  loadSuiviTournees(): void {
    this.suiviLoading.set(true);
    this.suiviError.set('');
    const filters: Record<string, any> = {};
    if (this.suiviDateDebut()) filters['date_debut']    = this.suiviDateDebut();
    if (this.suiviDateFin())   filters['date_fin']      = this.suiviDateFin();
    if (this.suiviAgence())    filters['agence']        = this.suiviAgence();
    if (this.suiviImmat())     filters['immatriculation'] = this.suiviImmat();
    this.carburantApi.getSuiviTournees(filters).subscribe({
      next: (r: any) => {
        this.suiviData.set(r.resultats ?? []);
        this.suiviCount.set(r.count ?? 0);
        this.suiviLoading.set(false);
      },
      error: () => {
        this.suiviError.set('Erreur lors du chargement.');
        this.suiviLoading.set(false);
      },
    });
  }

  // Couleur écart
  ecartClass(val: number | null): string {
    if (val === null || val === undefined) return '';
    if (val > 0) return 'ecart-pos';
    if (val < 0) return 'ecart-neg';
    return 'ecart-zero';
  }

  // Exporter suivi CSV
  exportSuiviCsv(): void {
    const rows = this.suiviData();
    if (!rows.length) return;
    const sep = ';'; const eol = '\r\n';
    const hdrs = [
      'Date','Véhicule','Tournée','Type véhicule',
      'KM Départ','KM Retour','KM Parcouru','KM Théorique',
      'Dotation réelle (L)','Dotation théorique (L)','Écart dotation (L)',
      'Montant réel (FCFA)','Montant théorique (FCFA)',
      'Conso réelle L/100','Conso théo L/100','Écart conso'
    ].join(sep);
    const data = rows.map(r => [
      r.date, r.immatriculation, r.tournee_libelle, r.type_vehicule,
      r.km_depart ?? 'N/A', r.km_retour ?? 'N/A', r.km_parcouru ?? 'N/A', r.km_theorique ?? 'N/A',
      r.vol_reel, r.vol_theorique ?? 'N/A', r.ecart_dotation ?? 'N/A',
      r.montant_reel, r.montant_theorique ?? 'N/A',
      r.conso_reel ?? 'N/A', r.conso_theorique ?? 'N/A', r.ecart_conso ?? 'N/A',
    ].join(sep)).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data,
      `suivi_tournees_${this.suiviDateDebut() || 'all'}.csv`);
  }
}
