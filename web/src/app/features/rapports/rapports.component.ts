// UbiFleet — Rapports & Statistiques (Angular 18)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, computed, ElementRef, ViewChild, DestroyRef
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { GroupeHub, HubCartesComponent } from '../../shared/hub-cartes/hub-cartes.component';
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
  imports: [RouterLink, DatePipe, DecimalPipe, HubCartesComponent],
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

  /** Rapport ouvert ; null = accueil en cartes. */
  activeTab   = signal<RapportTab | null>(null);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private destroyRef = inject(DestroyRef);
  private readonly rapportsInternes: RapportTab[] =
    ['dashboard', 'carburant', 'couts', 'multiagences', 'sinistres', 'interventions', 'pneus', 'effectif'];

  /** Rapports situés dans d'autres pages : la carte y mène directement. */
  private readonly liensExternes: Record<string, { route: string; params?: Record<string, string> }> = {
    conso_vehicules:  { route: '/carburant', params: { onglet: 'consommation' } },
    evolution_carb:   { route: '/carburant', params: { onglet: 'evolution' } },
    rapprochement:    { route: '/carburant', params: { onglet: 'rapprochement' } },
    classement:       { route: '/carburant', params: { onglet: 'chauffeurs' } },
    suivi_tournees:   { route: '/carburant', params: { onglet: 'suivi' } },
    anomalies:        { route: '/carburant', params: { onglet: 'anomalies' } },
    restitution:      { route: '/restitution-mensuelle' },
    utilisation:      { route: '/releves-km', params: { onglet: 'utilisation' } },
    etat_depenses:    { route: '/budget', params: { onglet: 'depenses' } },
    budget:           { route: '/budget', params: { onglet: 'tableau' } },
    etat_parc:        { route: '/etat-parc' },
  };

  readonly catalogue: GroupeHub[] = [
    { titre: "Vue d'ensemble", icone: 'fas fa-tachometer-alt', teinte: 'bleu', cartes: [
      { cle: 'dashboard', libelle: 'Tableau de bord', icone: 'fas fa-tachometer-alt',
        description: 'Indicateurs clés du mois : parc, carburant, coûts, alertes' },
      { cle: 'multiagences', libelle: 'Comparatif agences', icone: 'fas fa-sitemap',
        description: 'Véhicules, carburant et coûts par agence' },
      { cle: 'effectif', libelle: 'Effectif du parc', icone: 'fas fa-th-large',
        description: 'Répartition des véhicules par statut, type et agence' },
      { cle: 'etat_parc', libelle: 'État du parc', icone: 'fas fa-clipboard-list',
        description: 'Échéances : révisions, pneus, documents' },
      { cle: 'utilisation', libelle: 'Utilisation du parc', icone: 'fas fa-road',
        description: 'Km parcourus, véhicules sous-utilisés, coût au km' },
    ]},
    { titre: 'Carburant', icone: 'fas fa-gas-pump', teinte: 'orange', cartes: [
      { cle: 'carburant', libelle: 'Synthèse carburant', icone: 'fas fa-gas-pump',
        description: 'Litres, montants et consommation de la période' },
      { cle: 'conso_vehicules', libelle: 'Consommation par véhicule', icone: 'fas fa-tachometer-alt',
        description: 'L/100 km, écart à la référence, coût au km' },
      { cle: 'evolution_carb', libelle: 'Évolution par agence', icone: 'fas fa-chart-line',
        description: 'Consommation et dépenses mois par mois' },
      { cle: 'classement', libelle: 'Classement des chauffeurs', icone: 'fas fa-trophy',
        description: 'Consommation et écarts par chauffeur' },
      { cle: 'suivi_tournees', libelle: 'Suivi des tournées', icone: 'fas fa-route',
        description: 'Litres consommés par tournée et hors tournée' },
      { cle: 'anomalies', libelle: 'Anomalies de consommation', icone: 'fas fa-exclamation-triangle',
        description: 'Prises de carburant anormales à vérifier' },
      { cle: 'rapprochement', libelle: 'Rapprochement Total', icone: 'fas fa-balance-scale',
        description: 'Prises saisies face aux transactions Total' },
      { cle: 'restitution', libelle: 'Restitution mensuelle', icone: 'fas fa-file-invoice',
        description: 'Consommation facturée par véhicule et par mois' },
    ]},
    { titre: 'Coûts & budget', icone: 'fas fa-coins', teinte: 'vert', cartes: [
      { cle: 'couts', libelle: 'Coûts annuels', icone: 'fas fa-coins',
        description: 'Coût total par catégorie, agence et véhicule' },
      { cle: 'etat_depenses', libelle: 'État des dépenses', icone: 'fas fa-receipt',
        description: 'Toutes les dépenses filtrées, par poste, catégorie et origine' },
      { cle: 'budget', libelle: 'Budget prévu / réalisé', icone: 'fas fa-wallet',
        description: 'Suivi du budget annuel par poste' },
    ]},
    { titre: 'Entretien & sinistres', icone: 'fas fa-tools', teinte: 'rouge', cartes: [
      { cle: 'interventions', libelle: 'Interventions', icone: 'fas fa-tools',
        description: 'Interventions par type, coût et prestataire' },
      { cle: 'pneus', libelle: 'Pneus', icone: 'fas fa-circle-notch',
        description: 'Pneus montés, usure et remplacements' },
      { cle: 'sinistres', libelle: 'Sinistres', icone: 'fas fa-car-crash',
        description: 'Sinistres par type, mois et coût' },
    ]},
  ];

  /** Libellé du rapport ouvert (fil d'Ariane). */
  rapportOuvert = computed(() => {
    for (const g of this.catalogue) {
      const c = g.cartes.find(x => x.cle === this.activeTab());
      if (c) return { groupe: g.titre, libelle: c.libelle };
    }
    return null;
  });

  ouvrirRapport(cle: string | null): void {
    const externe = cle ? this.liensExternes[cle] : undefined;
    if (externe) { this.router.navigate([externe.route], { queryParams: externe.params ?? {} }); return; }
    this.router.navigate([], { relativeTo: this.route, queryParams: { rapport: cle || null } });
  }
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
    // Rapport de l'URL (?rapport=…), suivi aussi par « Précédent / Suivant »
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(q => {
      const r = q.get('rapport') as RapportTab | null;
      if (r && this.rapportsInternes.includes(r)) this.onTabChange(r);
      else { this.destroyCharts(); this.activeTab.set(null); }
    });
  }

  ngOnDestroy(): void { this.destroyCharts(); }

  onTabChange(tab: RapportTab): void {
    if (this.activeTab() !== tab) this.destroyCharts();
    this.activeTab.set(tab);
    // Données rechargées à chaque ouverture : à jour, et graphiques redessinés
    const chargements: Record<RapportTab, () => void> = {
      dashboard: () => this.loadDashboard(), carburant: () => this.loadCarburant(),
      couts: () => this.loadCouts(), multiagences: () => this.loadMultiAgences(),
      sinistres: () => this.loadSinistres(), interventions: () => this.loadInterventions(),
      pneus: () => this.loadPneus(), effectif: () => this.loadEffectif(),
    };
    chargements[tab]();
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
