// UbiFleet — Rapports & Statistiques (Angular 18)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, ElementRef, ViewChild
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import {
  RapportApiService, AgenceApiService, ChauffeurApiService
} from '../../core/services/api.service';
import { DashboardData } from '../../core/models';

type RapportTab = 'dashboard' | 'carburant' | 'couts' | 'multiagences'
                | 'sinistres' | 'interventions' | 'pneus' | 'effectif';

const MOIS = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'];
const CHART_COLORS = ['#092440','#5bd988','#3b82f6','#f59e0b','#ef4444',
                      '#8b5cf6','#06b6d4','#84cc16','#f97316','#ec4899'];

@Component({
  selector: 'ubi-rapports',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './rapports.component.html',
  styleUrls: ['./rapports.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RapportsComponent implements OnInit, OnDestroy {
  @ViewChild('chartCoutsCanvas')   chartCoutsCanvas?:  ElementRef<HTMLCanvasElement>;
  @ViewChild('chartParCatCanvas')  chartParCatCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartSinCanvas')     chartSinCanvas?:    ElementRef<HTMLCanvasElement>;
  @ViewChild('chartIntCanvas')     chartIntCanvas?:    ElementRef<HTMLCanvasElement>;
  @ViewChild('chartPneusCanvas')   chartPneusCanvas?:  ElementRef<HTMLCanvasElement>;

  private api        = inject(RapportApiService);
  private agenceApi  = inject(AgenceApiService);
  private chauffeurApi = inject(ChauffeurApiService);

  activeTab   = signal<RapportTab>('dashboard');
  agences     = signal<{ id: string; nom: string }[]>([]);
  chauffeurs  = signal<{ id: string; nom_complet: string }[]>([]);
  moisNoms    = MOIS;
  moisActuel  = new Date().getMonth() + 1;
  anneeActuelle = new Date().getFullYear();

  // Filtres communs dashboard/carburant/coûts
  filtreMois   = signal(this.moisActuel);
  filtreAnnee  = signal(this.anneeActuelle);
  filtreAgence = signal('');

  // Filtres sinistres/interventions/pneus
  filtreDebut  = signal('');
  filtreFin    = signal('');
  filtreImmat  = signal('');
  filtreAgence2= signal('');
  filtreChauff = signal('');
  filtreCateg  = signal('');

  // États données
  dashLoading  = signal(false); dashData  = signal<DashboardData | null>(null); dashError  = signal('');
  carbLoading  = signal(false); carbData  = signal<any>(null);                  carbError  = signal('');
  coutsLoading = signal(false); coutsData = signal<any>(null);                  coutsError = signal('');
  maLoading    = signal(false); maData    = signal<any>(null);                  maError    = signal('');
  sinLoading   = signal(false); sinData   = signal<any>(null);                  sinError   = signal('');
  intLoading   = signal(false); intData   = signal<any>(null);                  intError   = signal('');
  pnLoading    = signal(false); pnData    = signal<any>(null);                  pnError    = signal('');

  private charts: any[] = [];

  get annees(): number[] {
    const a = this.anneeActuelle;
    return [a, a-1, a-2, a-3];
  }

  ngOnInit(): void {
    this.agenceApi.getAll().subscribe({
      next: (res: any) => this.agences.set(res.results ?? res ?? []),
      error: () => {},
    });
    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res: any) => this.chauffeurs.set((res.results ?? []).map((c: any) => ({
        id: c.id, nom_complet: c.nom_complet
      }))),
      error: () => {},
    });
    this.loadDashboard();
  }

  ngOnDestroy(): void { this.destroyCharts(); }

  onTabChange(tab: RapportTab): void {
    this.activeTab.set(tab);
    if (tab === 'dashboard'    && !this.dashData())  this.loadDashboard();
    if (tab === 'carburant'    && !this.carbData())  this.loadCarburant();
    if (tab === 'couts'        && !this.coutsData()) this.loadCouts();
    if (tab === 'multiagences' && !this.maData())    this.loadMultiAgences();
    if (tab === 'sinistres'    && !this.sinData())   this.loadSinistres();
    if (tab === 'interventions'&& !this.intData())   this.loadInterventions();
    if (tab === 'pneus'        && !this.pnData())    this.loadPneus();
    if (tab === 'effectif'     && !this.effData())   this.loadEffectif();
  }

  onFiltre(field: string, e: Event): void {
    const val = (e.target as HTMLSelectElement | HTMLInputElement).value;
    if (field === 'mois')    this.filtreMois.set(+val);
    if (field === 'annee')   this.filtreAnnee.set(+val);
    if (field === 'agence')  this.filtreAgence.set(val);
    this.refreshCurrent();
  }

  onFiltre2(field: string, e: Event): void {
    const val = (e.target as HTMLSelectElement | HTMLInputElement).value;
    if (field === 'debut')   this.filtreDebut.set(val);
    if (field === 'fin')     this.filtreFin.set(val);
    if (field === 'immat')   this.filtreImmat.set(val);
    if (field === 'agence')  this.filtreAgence2.set(val);
    if (field === 'chauff')  this.filtreChauff.set(val);
    if (field === 'categ')   this.filtreCateg.set(val);
  }

  refreshCurrent(): void {
    const t = this.activeTab();
    if (t === 'dashboard')    this.loadDashboard();
    if (t === 'carburant')    this.loadCarburant();
    if (t === 'couts')        this.loadCouts();
    if (t === 'multiagences') this.loadMultiAgences();
  }

  buildParams(): Record<string, any> {
    const p: Record<string, any> = { mois: this.filtreMois(), annee: this.filtreAnnee() };
    if (this.filtreAgence()) p['agence'] = this.filtreAgence();
    return p;
  }

  buildParams2(): Record<string, any> {
    const p: Record<string, any> = {};
    if (this.filtreDebut())  p['date_debut']      = this.filtreDebut();
    if (this.filtreFin())    p['date_fin']         = this.filtreFin();
    if (this.filtreImmat())  p['immatriculation']  = this.filtreImmat();
    if (this.filtreAgence2())p['agence']           = this.filtreAgence2();
    if (this.filtreChauff()) p['chauffeur']        = this.filtreChauff();
    if (this.filtreCateg())  p['categorie']        = this.filtreCateg();
    return p;
  }

  // ── Dashboard ──────────────────────────────────────────────────────
  loadDashboard(): void {
    this.dashLoading.set(true); this.dashError.set('');
    this.api.getDashboard(this.buildParams()).subscribe({
      next: (d) => { this.dashData.set(d); this.dashLoading.set(false);
                     setTimeout(() => this.renderDashChart(), 80); },
      error: () => { this.dashError.set('Erreur chargement.'); this.dashLoading.set(false); },
    });
  }

  renderDashChart(): void {
    this.destroyChartByRef(this.chartCoutsCanvas);
    const d = this.dashData();
    if (!d?.cout_mensuel || !this.chartCoutsCanvas?.nativeElement) return;
    this.loadChartJs(() => {
      const Chart = (window as any)['Chart'];
      if (!Chart) return;
      this.charts.push(new Chart(this.chartCoutsCanvas!.nativeElement, {
        type: 'line',
        data: {
          labels: d.cout_mensuel.map((m: any) => `${MOIS[m.mois-1]} ${m.annee}`),
          datasets: [{ label: 'Coûts (FCFA)', data: d.cout_mensuel.map((m: any) => m.total),
            borderColor: '#092440', backgroundColor: '#09244015',
            borderWidth: 2.5, pointRadius: 4, fill: true, tension: 0.35 }],
        },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { ticks: { callback: (v: number) => v.toLocaleString('fr-FR') + ' F' } } } },
      }));
    });
  }

  // ── Carburant ──────────────────────────────────────────────────────
  loadCarburant(): void {
    this.carbLoading.set(true); this.carbError.set('');
    this.api.getCarburant(this.buildParams()).subscribe({
      next: (d) => { this.carbData.set(d); this.carbLoading.set(false); },
      error: () => { this.carbError.set('Erreur.'); this.carbLoading.set(false); },
    });
  }

  // ── Coûts ──────────────────────────────────────────────────────────
  loadCouts(): void {
    this.coutsLoading.set(true); this.coutsError.set('');
    this.api.getCouts({ annee: this.filtreAnnee(), agence: this.filtreAgence() || undefined }).subscribe({
      next: (d) => { this.coutsData.set(d); this.coutsLoading.set(false);
                     setTimeout(() => this.renderCoutsChart(), 80); },
      error: () => { this.coutsError.set('Erreur.'); this.coutsLoading.set(false); },
    });
  }

  renderCoutsChart(): void {
    this.destroyChartByRef(this.chartParCatCanvas);
    const d = this.coutsData();
    if (!d?.par_categorie?.length || !this.chartParCatCanvas?.nativeElement) return;
    this.loadChartJs(() => {
      const Chart = (window as any)['Chart'];
      if (!Chart) return;
      const cats = d.par_categorie;
      this.charts.push(new Chart(this.chartParCatCanvas!.nativeElement, {
        type: 'doughnut',
        data: { labels: cats.map((c: any) => c.libelle || c.categorie || 'Autre'),
          datasets: [{ data: cats.map((c: any) => c.total),
            backgroundColor: CHART_COLORS.slice(0, cats.length), borderWidth: 2, borderColor: '#fff' }] },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } } },
      }));
    });
  }

  // ── Multi-agences ──────────────────────────────────────────────────
  loadMultiAgences(): void {
    this.maLoading.set(true); this.maError.set('');
    this.api.getMultiAgences({ annee: this.filtreAnnee() }).subscribe({
      next: (d) => { this.maData.set(d); this.maLoading.set(false); },
      error: () => { this.maError.set('Erreur.'); this.maLoading.set(false); },
    });
  }

  // ── Sinistres ──────────────────────────────────────────────────────
  loadSinistres(): void {
    this.sinLoading.set(true); this.sinError.set('');
    this.api.getSinistres(this.buildParams2()).subscribe({
      next: (d) => { this.sinData.set(d); this.sinLoading.set(false);
                     setTimeout(() => this.renderSinChart(), 80); },
      error: () => { this.sinError.set('Erreur.'); this.sinLoading.set(false); },
    });
  }

  renderSinChart(): void {
    this.destroyChartByRef(this.chartSinCanvas);
    const d = this.sinData();
    if (!d?.par_mois?.length || !this.chartSinCanvas?.nativeElement) return;
    this.loadChartJs(() => {
      const Chart = (window as any)['Chart'];
      if (!Chart) return;
      this.charts.push(new Chart(this.chartSinCanvas!.nativeElement, {
        type: 'bar',
        data: {
          labels: d.par_mois.map((m: any) => `${m.mois_nom} ${m.date_sinistre__year}`),
          datasets: [{ label: 'Nb sinistres', data: d.par_mois.map((m: any) => m.nb),
            backgroundColor: '#ef444480', borderColor: '#ef4444', borderWidth: 1.5 }],
        },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
      }));
    });
  }

  // ── Interventions ──────────────────────────────────────────────────
  loadInterventions(): void {
    this.intLoading.set(true); this.intError.set('');
    this.api.getInterventions(this.buildParams2()).subscribe({
      next: (d) => { this.intData.set(d); this.intLoading.set(false);
                     setTimeout(() => this.renderIntChart(), 80); },
      error: () => { this.intError.set('Erreur.'); this.intLoading.set(false); },
    });
  }

  renderIntChart(): void {
    this.destroyChartByRef(this.chartIntCanvas);
    const d = this.intData();
    if (!d?.par_mois?.length || !this.chartIntCanvas?.nativeElement) return;
    this.loadChartJs(() => {
      const Chart = (window as any)['Chart'];
      if (!Chart) return;
      this.charts.push(new Chart(this.chartIntCanvas!.nativeElement, {
        type: 'bar',
        data: {
          labels: d.par_mois.map((m: any) => `${m.mois_nom} ${m.date_planifiee__year}`),
          datasets: [
            { label: 'Nb interventions', data: d.par_mois.map((m: any) => m.nb),
              backgroundColor: '#3b82f680', borderColor: '#3b82f6', borderWidth: 1.5 },
          ],
        },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
      }));
    });
  }

  // ── Pneus ──────────────────────────────────────────────────────────
  loadPneus(): void {
    this.pnLoading.set(true); this.pnError.set('');
    this.api.getPneus(this.buildParams2()).subscribe({
      next: (d) => { this.pnData.set(d); this.pnLoading.set(false);
                     setTimeout(() => this.renderPneusChart(), 80); },
      error: () => { this.pnError.set('Erreur.'); this.pnLoading.set(false); },
    });
  }

  renderPneusChart(): void {
    this.destroyChartByRef(this.chartPneusCanvas);
    const d = this.pnData();
    if (!d?.par_statut?.length || !this.chartPneusCanvas?.nativeElement) return;
    this.loadChartJs(() => {
      const Chart = (window as any)['Chart'];
      if (!Chart) return;
      this.charts.push(new Chart(this.chartPneusCanvas!.nativeElement, {
        type: 'doughnut',
        data: {
          labels: d.par_statut.map((s: any) => s.libelle),
          datasets: [{ data: d.par_statut.map((s: any) => s.nb),
            backgroundColor: ['#5bd988','#f59e0b','#092440'], borderWidth: 2, borderColor: '#fff' }],
        },
        options: { responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'right' } } },
      }));
    });
  }

  // ── Helpers ────────────────────────────────────────────────────────
  nomMois(m: number): string { return MOIS[m-1] ?? ''; }
  getColor(i: number): string { return CHART_COLORS[i % CHART_COLORS.length]; }
  dispatcheur(v: number | null | undefined): number { return Number(v || 0); }
  getMaxVal(arr: any[], key: string): number {
    if (!arr.length) return 1;
    return Math.max(...arr.map(a => Number(a[key] || 0))) || 1;
  }

  exportCarburantCsv(): void {
    const d = this.carbData();
    if (!d) return;
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Immatriculation','Marque','Modèle','Agence','Volume (L)',
                  'Montant (FCFA)','Nb prises de carburant','Conso moy (L/100km)','Conso de référence','Écart %'].join(sep);
    const rows = (d.par_vehicule ?? []).map((r: any) =>
      [r.vehicule__immatriculation, r.vehicule__marque__libelle, r.vehicule__modele__libelle,
       r.agence__nom ?? '', r.total_litres, r.total_fcfa, r.nb_pleins, r.conso_moy ?? '',
       r.conso_reference ?? '', r.ecart_pct ?? ''].join(sep)
    ).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + rows,
      `carburant_${this.filtreMois()}_${this.filtreAnnee()}.csv`);
  }

  private destroyChartByRef(ref?: ElementRef): void {
    if (!ref) return;
    const idx = this.charts.findIndex(c => c.canvas === ref.nativeElement);
    if (idx >= 0) { try { this.charts[idx].destroy(); } catch (_) {} this.charts.splice(idx, 1); }
  }

  private destroyCharts(): void {
    this.charts.forEach(c => { try { c.destroy(); } catch (_) {} });
    this.charts = [];
  }

  private loadChartJs(cb: () => void): void {
    if ((window as any)['Chart']) { cb(); return; }
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
    s.onload = cb;
    document.head.appendChild(s);
  }

  private downloadCsv(csv: string, filename: string): void {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click(); URL.revokeObjectURL(a.href);
  }

  // ── Effectif parc ────────────────────────────────────────────────
  effData      = signal<any>(null);
  effLoading   = signal(false);
  effError     = signal('');
  effAgence    = signal('');
  effActif     = signal('true');

  loadEffectif(): void {
    this.effLoading.set(true);
    this.effError.set('');
    const params: Record<string, any> = { actif: this.effActif() };
    if (this.effAgence()) params['agence'] = this.effAgence();
    this.api.getEffectifParc(params).subscribe({
      next: (r: any) => { this.effData.set(r); this.effLoading.set(false); },
      error: () => { this.effError.set('Erreur lors du chargement.'); this.effLoading.set(false); },
    });
  }

  onFiltreEffectif(field: string, e: Event): void {
    const val = (e.target as HTMLSelectElement).value;
    if (field === 'agence') this.effAgence.set(val);
    if (field === 'actif')  this.effActif.set(val);
    this.loadEffectif();
  }

  // Les 7 groupements pour itération dans le template
  effGroupes(): { titre: string; icone: string; rows: any[] }[] {
    const d = this.effData();
    if (!d) return [];
    return [
      { titre: 'Par agence',    icone: 'fas fa-building',      rows: d.par_agence    ?? [] },
      { titre: 'Par marque',    icone: 'fas fa-copyright',     rows: d.par_marque    ?? [] },
      { titre: 'Par modèle',    icone: 'fas fa-car-side',      rows: d.par_modele    ?? [] },
      { titre: 'Par type',      icone: 'fas fa-truck',          rows: d.par_type      ?? [] },
      { titre: 'Par carburant', icone: 'fas fa-gas-pump',       rows: d.par_carburant ?? [] },
      { titre: 'Par statut',    icone: 'fas fa-circle',         rows: d.par_statut    ?? [] },
      { titre: 'Par usage',     icone: 'fas fa-tag',            rows: d.par_usage     ?? [] },
    ];
  }

  exportEffectifCsv(): void {
    const d = this.effData();
    if (!d) return;
    const sep = ';'; const eol = '\r\n';
    let csv = 'Groupement' + sep + 'Valeur' + sep + 'Nombre' + sep + 'Pourcentage' + eol;
    this.effGroupes().forEach(g => {
      g.rows.forEach((r: any) => {
        csv += [g.titre, r.label, r.nb, r.pct + '%'].join(sep) + eol;
      });
    });
    this.downloadCsv('\uFEFF' + csv, 'effectif_parc.csv');
  }
}
