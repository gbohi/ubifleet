// UbiFleet — Rapports & Statistiques (Angular 18)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, computed, ElementRef, ViewChild, DestroyRef
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { GroupeHub, HubCartesComponent } from '../../shared/hub-cartes/hub-cartes.component';
import { OptionRecherche, SelectRechercheComponent } from '../../shared/select-recherche/select-recherche.component';
import { OptionsSaisieService } from '../../core/services/options-saisie.service';
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
  imports: [RouterLink, DatePipe, DecimalPipe, HubCartesComponent, SelectRechercheComponent],
  templateUrl: './rapports.component.html',
  styleUrls: ['./rapports.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RapportsComponent implements OnInit, OnDestroy {
  @ViewChild('chartCoutsCanvas')   chartCoutsCanvas?:  ElementRef<HTMLCanvasElement>;
  @ViewChild('chartParCatCanvas')  chartParCatCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartEvolCoutsCanvas') chartEvolCoutsCanvas?: ElementRef<HTMLCanvasElement>;
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
    budget:           { route: '/budget', params: { onglet: 'budgets' } },
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
  /** Véhicules proposés au filtre d'immatriculation (valeur = immatriculation). */
  vehiculesImmat = signal<OptionRecherche[]>([]);
  private options = inject(OptionsSaisieService);
  /** Rapports filtrés par mois / année / agence (les autres ont leurs propres filtres). */
  avecFiltresPeriode = computed(() => ['dashboard', 'carburant', 'couts', 'multiagences'].includes(this.activeTab() ?? ''));
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
    this.options.vehicules().subscribe({
      next: l => this.vehiculesImmat.set(l.map(v => ({ value: v.label, label: v.label }))),   // label = immatriculation
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
    this.destroyChartByRef(this.chartEvolCoutsCanvas);
    const d = this.coutsData();
    if (!d) return;
    this.loadChartJs(() => {
      const Chart = (window as any)['Chart'];
      if (!Chart) return;
      const fcfa = (v: number) => Math.round(v).toLocaleString('fr-FR');
      if (this.chartEvolCoutsCanvas?.nativeElement && d.evolution?.length) {
        this.charts.push(new Chart(this.chartEvolCoutsCanvas.nativeElement, {
          data: {
            labels: d.evolution.map((m: any) => MOIS[m.mois - 1]),
            datasets: [
              { type: 'bar', label: String(d.annee), data: d.evolution.map((m: any) => m.total),
                backgroundColor: '#5bd988', borderRadius: 4, order: 2 },
              { type: 'bar', label: String(d.annee - 1), data: d.evolution.map((m: any) => m.total_precedent),
                backgroundColor: '#c9d3df', borderRadius: 4, order: 3 },
              { type: 'line', label: `Cumul ${d.annee}`, data: d.evolution.map((m: any) => m.cumul), yAxisID: 'cumul',
                borderColor: '#092440', backgroundColor: '#092440', borderWidth: 2, pointRadius: 2, tension: 0.3, order: 1 },
            ],
          },
          options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } },
                       tooltip: { callbacks: { label: (c: any) => `${c.dataset.label} : ${fcfa(c.raw)} FCFA` } } },
            scales: { y: { beginAtZero: true, ticks: { callback: (v: number) => fcfa(v) } },
                      cumul: { position: 'right', beginAtZero: true, grid: { display: false },
                               ticks: { callback: (v: number) => fcfa(v) } } } },
        }));
      }
      const cats = d.par_categorie ?? [];
      if (this.chartParCatCanvas?.nativeElement && cats.length) {
        this.charts.push(new Chart(this.chartParCatCanvas.nativeElement, {
          type: 'doughnut',
          data: { labels: cats.map((c: any) => c.libelle || c.categorie || 'Autre'),
            datasets: [{ data: cats.map((c: any) => c.total),
              backgroundColor: CHART_COLORS.slice(0, cats.length), borderWidth: 2, borderColor: '#fff' }] },
          options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'right', labels: { font: { size: 11 } } },
                       tooltip: { callbacks: { label: (c: any) => `${c.label} : ${fcfa(c.raw)} FCFA` } } } },
        }));
      }
    });
  }

  /** Rapport des coûts en CSV (Excel) : indicateurs, budget par poste, répartitions, mois, véhicules. */
  exporterCouts(): void {
    const d = this.coutsData();
    if (!d) return;
    const cell = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const ligne = (...cols: any[]) => cols.map(cell).join(';');
    const n = (v: any) => String(Math.round(Number(v) || 0));
    const p = (v: any) => v === null || v === undefined ? '' : String(v).replace('.', ',');
    const agence = this.agences().find((a: any) => a.id === this.filtreAgence())?.nom ?? 'Toutes les agences';
    const lignes = [
      ligne(`Coûts annuels ${d.annee} — ${agence}`), '',
      ligne('Coût total (FCFA)', n(d.total)), ligne('Nombre de dépenses', d.nb),
      ligne(`Coût total ${d.annee - 1} (FCFA)`, n(d.total_precedent)), ligne('Variation (%)', p(d.variation)),
      ligne('Budget prévu (FCFA)', n(d.budget_total)), ligne('Budget consommé (%)', p(d.taux_budget)),
      ligne('Coût moyen par véhicule (FCFA)', n(d.cout_moyen_vehicule)), '',
      ligne('Poste', 'Prévu', 'Réalisé', 'Écart', 'Consommé (%)'),
      ...d.budget.map((b: any) => ligne(b.libelle, n(b.prevu), n(b.realise), n(b.ecart), p(b.taux))), '',
      ligne('Mois', String(d.annee), String(d.annee - 1), `Cumul ${d.annee}`),
      ...d.evolution.map((m: any) => ligne(MOIS[m.mois - 1], n(m.total), n(m.total_precedent), n(m.cumul))), '',
      ligne('Catégorie', 'Poste', 'Nb', 'Montant', 'Part (%)'),
      ...d.par_categorie.map((c: any) => ligne(c.libelle, c.poste_libelle, c.nb, n(c.total), p(c.part))), '',
      ligne('Origine', 'Nb', 'Montant', 'Part (%)'),
      ...d.par_origine.map((o: any) => ligne(o.libelle, o.nb, n(o.total), p(o.part))), '',
      ligne('Agence', 'Nb', 'Montant', 'Part (%)'),
      ...d.par_agence.map((a: any) => ligne(a.agence, a.nb, n(a.total), p(a.part))), '',
      ligne('Véhicule', 'Désignation', ...d.postes.map((x: any) => x.libelle), 'Total'),
      ...d.top_vehicules.map((v: any) => ligne(v.immatriculation, v.designation,
        ...d.postes.map((x: any) => n(v.postes[x.poste])), n(v.total))),
    ];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + lignes.join('\r\n')], { type: 'text/csv;charset=utf-8;' }));
    a.download = `couts-${d.annee}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
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

  // ── Exports Excel (CSV ; séparateur « ; », décimales à la virgule) ──
  /** Un fichier en sections : titre, en-têtes puis lignes, séparées par une ligne vide. */
  private exporterSections(fichier: string, titre: string, sections: { titre?: string; entetes: string[]; lignes: any[][] }[],
                           resume?: string): void {
    const cell = (v: any) => {
      const t = typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(2).replace('.', ',')) : String(v ?? '');
      return `"${t.replace(/"/g, '""')}"`;
    };
    const ligne = (cols: any[]) => cols.map(cell).join(';');
    const contenu: string[] = [ligne([titre]), ligne([resume ?? this.resumeFiltresRapport()]), ''];
    for (const sct of sections) {
      if (sct.titre) contenu.push(ligne([sct.titre]));
      contenu.push(ligne(sct.entetes), ...sct.lignes.map(ligne), '');
    }
    this.downloadCsv('\uFEFF' + contenu.join('\r\n'), fichier);
  }

  private nombre(v: any): number { return Number(v) || 0; }

  /** Filtres appliqués au rapport ouvert, pour l'en-tête des exports. */
  private resumeFiltresRapport(): string {
    const agence = (id: string) => this.agences().find((a: any) => a.id === id)?.nom;
    if (this.avecFiltresPeriode()) {
      const t = this.activeTab();
      const periode = t === 'dashboard' || t === 'carburant' ? `${MOIS[this.filtreMois() - 1]} ${this.filtreAnnee()}` : `Année ${this.filtreAnnee()}`;
      return [periode, t !== 'multiagences' ? (agence(this.filtreAgence()) ?? 'Toutes les agences') : ''].filter(Boolean).join(' · ');
    }
    const fr = (d: string) => d.split('-').reverse().join('/');
    const morceaux = [
      this.filtreDebut() || this.filtreFin() ? `Du ${this.filtreDebut() ? fr(this.filtreDebut()) : '…'} au ${this.filtreFin() ? fr(this.filtreFin()) : '…'}` : 'Toutes dates',
      this.filtreImmat() ? `Véhicule ${this.filtreImmat()}` : '',
      agence(this.filtreAgence2()) ?? '',
      this.chauffeurs().find(c => c.id === this.filtreChauff())?.nom_complet ?? '',
    ];
    return morceaux.filter(Boolean).join(' · ');
  }

  exporterDashboard(): void {
    const d = this.dashData() as any;
    if (!d) return;
    const n = (v: any) => this.nombre(v);
    this.exporterSections(`tableau_de_bord_${this.filtreMois()}_${this.filtreAnnee()}.csv`, 'Tableau de bord UbiFleet', [
      { titre: 'Parc', entetes: ['Indicateur', 'Valeur'], lignes: [
        ['Véhicules actifs', d.parc.total], ['En service', d.parc.en_service], ['En révision', d.parc.en_revision],
        ['Immobilisés / en panne / accidentés', d.parc.immobilises], ['Sinistres en cours', d.sinistres.en_cours],
        ['Sinistres de l\'année', d.sinistres.annee], ['Alertes actives', d.alertes.total],
        ['Assurances expirant dans 30 jours', d.assurances_critiques], ['Véhicules avec assurance expirée', d.assurances_expirees ?? 0]] },
      { titre: 'Carburant du mois', entetes: ['Indicateur', 'Valeur'], lignes: [
        ['Volume (L)', n(d.carburant.volume)], ['Montant (FCFA)', n(d.carburant.montant)],
        ['Prises de carburant', d.carburant.nb_pleins], ['Consommation moyenne (L/100 km)', n(d.carburant.conso_moy)],
        ['Anomalies', d.carburant.anomalies]] },
      { titre: 'Entretien du mois', entetes: ['Indicateur', 'Valeur'], lignes: [
        ['Interventions planifiées', d.entretien.planifiees], ['Terminées', d.entretien.terminees],
        ['En cours', d.entretien.en_cours], ['Coût des interventions terminées (FCFA)', n(d.entretien.cout)]] },
      { titre: 'Coûts — 12 derniers mois', entetes: ['Mois', 'Montant (FCFA)'],
        lignes: (d.cout_mensuel ?? []).map((m: any) => [`${MOIS[m.mois - 1]} ${m.annee}`, n(m.total)]) },
      { titre: 'Répartition des coûts du mois', entetes: ['Catégorie', 'Montant (FCFA)'],
        lignes: (d.repartition_couts ?? []).map((r: any) => [r.label, n(r.montant)]) },
      { titre: 'Véhicules les plus consommateurs', entetes: ['Immatriculation', 'Marque', 'Modèle', 'Litres', 'Montant (FCFA)'],
        lignes: (d.top_consommation ?? []).map((v: any) => [v.vehicule__immatriculation, v.vehicule__marque__libelle ?? '',
          v.vehicule__modele__libelle ?? '', n(v.litres), n(v.montant)]) },
      { titre: 'Écarts à la consommation de référence', entetes: ['Immatriculation', 'Conso (L/100 km)', 'Référence', 'Écart (%)', 'Litres'],
        lignes: (d.top_ecart_conso ?? []).map((v: any) => [v.vehicule__immatriculation, n(v.conso), n(v.reference), n(v.ecart_pct), n(v.litres)]) },
    ]);
  }

  exporterMultiAgences(): void {
    const d = this.maData();
    if (!d) return;
    const total = (d.agences ?? []).reduce((a: number, x: any) => a + this.nombre(x.cout_total), 0);
    this.exporterSections(`comparatif_agences_${d.annee}.csv`, `Comparatif des agences — ${d.annee}`, [{
      entetes: ['Agence', 'Code', 'Véhicules', 'Coût total (FCFA)', 'Coût / véhicule (FCFA)', 'Carburant (L)', 'Carburant (FCFA)', 'Part du coût (%)'],
      lignes: (d.agences ?? []).map((a: any) => [a.agence_nom, a.agence_code, a.nb_vehicules, this.nombre(a.cout_total),
        this.nombre(a.cout_par_vehicule), this.nombre(a.carburant_litres), this.nombre(a.carburant_fcfa),
        total ? Math.round(this.nombre(a.cout_total) * 1000 / total) / 10 : 0]),
    }]);
  }

  exporterSinistres(): void {
    const d = this.sinData();
    if (!d) return;
    this.exporterSections('rapport_sinistres.csv', 'Rapport des sinistres', [
      { titre: 'Synthèse', entetes: ['Indicateur', 'Valeur'], lignes: [
        ['Sinistres', d.total], ['En cours', d.en_cours], ['Coût des réparations (FCFA)', this.nombre(d.cout_total)],
        ['Indemnisations reçues (FCFA)', this.nombre(d.indemnisation_total)], ['Reste à la charge (FCFA)', this.nombre(d.reste_a_charge)]] },
      { titre: 'Par type', entetes: ['Type', 'Nb', 'Réparation (FCFA)', 'Indemnisé (FCFA)', 'Reste à charge (FCFA)'],
        lignes: d.par_type.map((t: any) => [t.libelle, t.nb, t.cout, t.indemnisation, t.reste_a_charge]) },
      { titre: 'Par statut', entetes: ['Statut', 'Nb'], lignes: d.par_statut.map((x: any) => [x.libelle, x.nb]) },
      { titre: 'Par mois', entetes: ['Mois', 'Nb', 'Réparation (FCFA)'],
        lignes: d.par_mois.map((m: any) => [`${m.mois_nom} ${m.date_sinistre__year}`, m.nb, m.cout]) },
    ]);
  }

  exporterInterventions(): void {
    const d = this.intData();
    if (!d) return;
    this.exporterSections('rapport_interventions.csv', 'Rapport des interventions', [
      { titre: 'Synthèse', entetes: ['Indicateur', 'Valeur'], lignes: [
        ['Interventions', d.total], ['Coût réel des terminées (FCFA)', this.nombre(d.cout_total)],
        ['Coût estimé hors annulées (FCFA)', this.nombre(d.cout_estime_total)]] },
      { titre: 'Par statut', entetes: ['Statut', 'Nb'], lignes: d.par_statut.map((x: any) => [x.libelle, x.nb]) },
      { titre: 'Par catégorie', entetes: ['Catégorie', 'Nb', 'Coût (FCFA)'],
        lignes: d.par_categorie.map((c: any) => [c.libelle, c.nb, c.cout]) },
      { titre: "Par type d'intervention", entetes: ['Type', 'Catégorie', 'Nb', 'Coût (FCFA)'],
        lignes: d.par_type.map((t: any) => [t.type_intervention__nom, t.categorie_libelle, t.nb, t.cout]) },
      { titre: 'Par mois (date planifiée)', entetes: ['Mois', 'Nb', 'Coût (FCFA)'],
        lignes: d.par_mois.map((m: any) => [`${m.mois_nom} ${m.date_planifiee__year}`, m.nb, m.cout]) },
    ]);
  }

  exporterPneus(): void {
    const d = this.pnData();
    if (!d) return;
    this.exporterSections('rapport_pneus.csv', 'Rapport des pneus', [
      { titre: 'Synthèse', entetes: ['Indicateur', 'Valeur'], lignes: [['Pneus', d.total], ['Coût total (FCFA)', this.nombre(d.cout_total)]] },
      { titre: 'Par statut', entetes: ['Statut', 'Nb', 'Coût (FCFA)'], lignes: d.par_statut.map((x: any) => [x.libelle, x.nb, x.cout]) },
      { titre: 'Par position', entetes: ['Position', 'Nb', 'Coût (FCFA)'], lignes: d.par_position.map((x: any) => [x.libelle, x.nb, x.cout]) },
      { titre: 'Par marque', entetes: ['Marque', 'Nb', 'Coût (FCFA)'], lignes: d.par_marque.map((x: any) => [x.marque, x.nb, x.cout]) },
      { titre: 'Montages par mois', entetes: ['Mois', 'Nb', 'Coût (FCFA)'],
        lignes: d.par_mois.map((m: any) => [`${m.mois_nom} ${m.date_montage__year}`, m.nb, m.cout]) },
      { titre: 'Pneus à changer', entetes: ['Véhicule', 'Position', 'Marque', 'Km de remplacement'],
        lignes: d.urgents.map((u: any) => [u.vehicule__immatriculation, u.position_libelle, u.marque, u.kilometrage_remplacement ?? '']) },
    ]);
  }

  exportCarburantCsv(): void {
    const d = this.carbData();
    if (!d) return;
    const n = (v: any) => (v === null || v === undefined ? '' : this.nombre(v));
    this.exporterSections(`carburant_${this.filtreMois()}_${this.filtreAnnee()}.csv`, 'Synthèse carburant', [
      { titre: 'Synthèse', entetes: ['Indicateur', 'Valeur'], lignes: [
        ['Litres', n(d.global?.total_litres)], ['Montant (FCFA)', n(d.global?.total_fcfa)],
        ['Prises de carburant', d.global?.nb_pleins ?? 0], ['Consommation moyenne (L/100 km)', n(d.global?.conso_moy)]] },
      { titre: 'Par véhicule', entetes: ['Immatriculation', 'Marque', 'Modèle', 'Agence', 'Volume (L)', 'Montant (FCFA)',
          'Prises', 'Conso (L/100 km)', 'Référence', 'Écart (%)'],
        lignes: (d.par_vehicule ?? []).map((r: any) => [r.vehicule__immatriculation, r.vehicule__marque__libelle ?? '',
          r.vehicule__modele__libelle ?? '', r.agence__nom ?? '', n(r.total_litres), n(r.total_fcfa), r.nb_pleins,
          n(r.conso_moy), n(r.conso_reference), n(r.ecart_pct)]) },
      { titre: 'Par station', entetes: ['Station', 'Litres', 'Montant (FCFA)'],
        lignes: (d.par_station ?? []).map((r: any) => [r.station__nom, n(r.litres), n(r.total)]) },
      { titre: 'Anomalies', entetes: ['Véhicule', 'Date', 'Volume (L)', 'Montant (FCFA)', 'Conso calculée (L/100 km)'],
        lignes: (d.anomalies ?? []).map((r: any) => [r.vehicule__immatriculation, String(r.date_plein).split('-').reverse().join('/'),
          n(r.volume_litres), n(r.montant_fcfa), n(r.consommation_calculee)]) },
    ]);
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

  /** Chart.js chargé à la demande depuis l'application (pas de CDN). */
  private loadChartJs(cb: () => void): void {
    if ((window as any)['Chart']) { cb(); return; }
    import('chart.js/auto').then(m => { (window as any)['Chart'] = m.default; cb(); });
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
    const agence = this.agences().find((a: any) => a.id === this.effAgence())?.nom ?? 'Toutes les agences';
    this.exporterSections('effectif_parc.csv', `Effectif du parc — ${d.total} véhicule(s)`,
      this.effGroupes().map(g => ({ titre: g.titre, entetes: ['Valeur', 'Nombre', 'Part (%)'],
                                    lignes: g.rows.map((r: any) => [r.label, r.nb, Number(r.pct)]) })),
      `${agence} · ${this.effActif() === 'true' ? 'véhicules actifs' : 'actifs et archivés'}`);
  }

}
