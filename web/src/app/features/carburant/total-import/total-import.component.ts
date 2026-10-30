// UbiFleet — Transactions Total Carburant (Angular 18)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, computed, ElementRef, ViewChild
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpEventType } from '@angular/common/http';
import { TotalImportApiService } from '../../../core/services/api.service';

interface ImportResult {
  import_id: string; fichier: string; nb_lignes: number;
  importees: number; doublons: number; erreurs: number;
  lignes_erreur: { ligne: number; erreur: string; immatriculation: string }[];
}
interface ImportHistorique {
  id: string; fichier_nom: string; date_import: string;
  nb_lignes: number; nb_importees: number; nb_doublons: number;
  nb_erreurs: number; importe_par_nom: string | null;
}
interface ConsoVehicule {
  immatriculation: string; km_debut: number; km_fin: number;
  km_parcourus: number; volume_total: number; montant_total: number;
  nb_pleins: number; conso_100: number | null;
}
interface AgencePoint { mois: string; volume: number; montant: number; nb: number; }
interface AgenceSerie { nom: string; client: string; points: AgencePoint[]; }

type Tab = 'import' | 'historique' | 'transactions' | 'consommation' | 'evolution' | 'reconciliation';

const COLORS = [
  '#092440','#5bd988','#3b82f6','#f59e0b','#ef4444',
  '#8b5cf6','#06b6d4','#84cc16','#f97316','#ec4899',
];

@Component({
  selector: 'ubi-total-import',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './total-import.component.html',
  styleUrls: ['./total-import.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TotalImportComponent implements OnInit, OnDestroy {
  @ViewChild('chartCanvas') chartCanvas?: ElementRef<HTMLCanvasElement>;
  private api = inject(TotalImportApiService);

  activeTab     = signal<Tab>('import');
  isDragOver    = signal(false);
  selectedFile  = signal<File | null>(null);
  uploading     = signal(false);
  uploadPct     = signal(0);
  result        = signal<ImportResult | null>(null);
  importError   = signal('');
  historique    = signal<ImportHistorique[]>([]);
  historiqueLoad= signal(false);

  // ── Transactions ──
  transactions      = signal<any[]>([]);
  transactionsTotal = signal(0);
  transactionsLoad  = signal(false);
  transPage         = signal(1);
  transSearch       = signal('');
  transImmat        = signal('');
  transChauf        = signal('');
  transDateDebut    = signal('');
  transDateFin      = signal('');
  exporting         = signal(false);
  showColPicker     = signal(false);

  // ── Consommation ──
  consoDateDebut = signal('');
  consoDateFin   = signal('');
  consoImmat     = signal('');
  consoNumChauf  = signal('');
  consoLoading   = signal(false);
  consoData      = signal<ConsoVehicule[]>([]);
  consoError     = signal('');
  consoSortKey   = signal<string>('conso_100');
  consoSortAsc   = signal(false);

  // ── Évolution agences ──
  evoDateDebut = signal('');
  evoDateFin   = signal('');
  evoImmat     = signal('');
  evoNumChauf  = signal('');
  evoLoading   = signal(false);
  evoData      = signal<AgenceSerie[]>([]);
  evoError     = signal('');
  evoMetrique  = signal<'volume' | 'montant' | 'nb'>('volume');
  evoChart: any = null;

  // ── Réconciliation ──
  recoDateDebut = signal('');
  recoDateFin   = signal('');
  recoImmat     = signal('');
  recoNumChauf  = signal('');
  recoSeuilVol  = signal(5);
  recoSeuilMnt  = signal(5);
  recoLoading   = signal(false);
  recoError     = signal('');
  recoData      = signal<any>(null);
  recoFiltre    = signal<string>('');

  // ── Colonnes transactions ──
  readonly allColumns = [
    { key: 'date_transaction',      label: 'Date',            visible: true  },
    { key: 'heure_transaction',     label: 'Heure',           visible: true  },
    { key: 'immatriculation',       label: 'Immatriculation', visible: true  },
    { key: 'nom_chauffeur',         label: 'Chauffeur',       visible: true  },
    { key: 'numero_chauffeur',      label: 'N° Chauffeur',    visible: false },
    { key: 'nom_station',           label: 'Station',         visible: true  },
    { key: 'numero_station',        label: 'N° Station',      visible: false },
    { key: 'nom_produit',           label: 'Produit',         visible: true  },
    { key: 'prix_unitaire',         label: 'Prix unit.',      visible: true  },
    { key: 'volume',                label: 'Volume (L)',      visible: true  },
    { key: 'montant',               label: 'Montant (FCFA)',  visible: true  },
    { key: 'solde_avant',           label: 'Solde avant',     visible: false },
    { key: 'solde_apres',           label: 'Solde après',     visible: false },
    { key: 'montant_preautorise',   label: 'Pré-autorisé',   visible: false },
    { key: 'kilometrage_precedent', label: 'Km préc.',        visible: true  },
    { key: 'kilometrage_actuel',    label: 'Km actuel',       visible: true  },
    { key: 'numero_ticket',         label: 'N° Ticket',       visible: true  },
    { key: 'code_autorisation',     label: 'Code autori.',    visible: true  },
    { key: 'nom_transaction',       label: 'Type trans.',     visible: false },
    { key: 'nom_pompiste',          label: 'Pompiste',        visible: false },
    { key: 'numero_terminal',       label: 'N° Terminal',     visible: false },
    { key: 'statut_transaction',    label: 'Statut',          visible: true  },
    { key: 'bonus_mypass_utilise',  label: 'Bonus MyPass',    visible: false },
    { key: 'profil_transaction',    label: 'Profil',          visible: false },
    { key: 'nom_client',            label: 'Client',          visible: false },
    { key: 'nom_filiale',           label: 'Filiale',         visible: false },
    { key: 'nom_service',           label: 'Service',         visible: false },
  ];

  visibleColumns = signal<string[]>(
    this.allColumns.filter(c => c.visible).map(c => c.key)
  );

  consoSorted = computed(() => {
    const key = this.consoSortKey() as keyof ConsoVehicule;
    const asc  = this.consoSortAsc();
    return [...this.consoData()].sort((a, b) => {
      const va = (a[key] ?? 0) as number;
      const vb = (b[key] ?? 0) as number;
      return asc ? va - vb : vb - va;
    });
  });

  get totalPages(): number { return Math.ceil(this.transactionsTotal() / 20) || 1; }
  get pages(): number[] {
    const cur = this.transPage(), max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.loadHistorique();
    const now   = new Date();
    const debut = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    const fmt   = (d: Date) => d.toISOString().split('T')[0];
    this.consoDateDebut.set(fmt(debut));  this.consoDateFin.set(fmt(now));
    this.evoDateDebut.set(fmt(debut));    this.evoDateFin.set(fmt(now));
  }

  ngOnDestroy(): void {
    if (this.evoChart) { this.evoChart.destroy(); this.evoChart = null; }
  }

  onTabChange(tab: Tab): void {
    this.activeTab.set(tab);
    if (tab === 'transactions' && this.transactions().length === 0) this.loadTransactions();
    if (tab === 'historique') this.loadHistorique();
  }

  // ── Drag & Drop ──
  onDragOver(e: DragEvent): void { e.preventDefault(); this.isDragOver.set(true); }
  onDragLeave(): void             { this.isDragOver.set(false); }
  onDrop(e: DragEvent): void {
    e.preventDefault(); this.isDragOver.set(false);
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) this.setFile(files[0]);
  }
  onFileInput(e: Event): void {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) this.setFile(input.files[0]);
  }
  setFile(file: File): void {
    const ext = file.name.toLowerCase();
    if (!ext.endsWith('.csv') && !ext.endsWith('.xlsx') && !ext.endsWith('.xls')) {
      this.importError.set('Format non supporté. Utilisez CSV ou Excel (.xlsx, .xls).');
      return;
    }
    this.selectedFile.set(file); this.result.set(null); this.importError.set('');
  }
  clearFile(): void { this.selectedFile.set(null); this.result.set(null); this.importError.set(''); }
  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' Ko';
    return (bytes/(1024*1024)).toFixed(2) + ' Mo';
  }

  startImport(): void {
    const file = this.selectedFile();
    if (!file || this.uploading()) return;
    this.uploading.set(true); this.uploadPct.set(0);
    this.importError.set(''); this.result.set(null);
    const fd = new FormData(); fd.append('fichier', file);
    this.api.upload(fd).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total)
          this.uploadPct.set(Math.round(100 * event.loaded / event.total));
        else if (event.type === HttpEventType.Response) {
          this.uploading.set(false); this.uploadPct.set(100);
          this.result.set(event.body as ImportResult);
          this.selectedFile.set(null); this.loadHistorique();
        }
      },
      error: (err) => { this.uploading.set(false); this.importError.set(err?.error?.detail ?? "Erreur lors de l'import."); },
    });
  }

  loadHistorique(): void {
    this.historiqueLoad.set(true);
    this.api.getHistorique({ page_size: 50 }).subscribe({
      next: (res) => { this.historique.set(Array.isArray(res) ? res : (res.results ?? [])); this.historiqueLoad.set(false); },
      error: () => this.historiqueLoad.set(false),
    });
  }

  buildTransFilters(): Record<string, any> {
    const f: Record<string, any> = { page: this.transPage(), page_size: 20 };
    if (this.transSearch())    f['search']           = this.transSearch();
    if (this.transImmat())     f['immatriculation']  = this.transImmat();
    if (this.transChauf())     f['nom_chauffeur']    = this.transChauf();
    if (this.transDateDebut()) f['date_transaction'] = this.transDateDebut();
    if (this.transDateFin())   f['date_transaction_before'] = this.transDateFin();
    return f;
  }

  loadTransactions(): void {
    this.transactionsLoad.set(true);
    this.api.getTransactions(this.buildTransFilters()).subscribe({
      next: (res) => {
        this.transactions.set(res.results ?? []);
        this.transactionsTotal.set(res.count ?? 0);
        this.transactionsLoad.set(false);
      },
      error: () => this.transactionsLoad.set(false),
    });
  }

  onTransSearch(e: Event):    void { this.transSearch.set((e.target as HTMLInputElement).value);    this.transPage.set(1); this.loadTransactions(); }
  onTransImmat(e: Event):     void { this.transImmat.set((e.target as HTMLInputElement).value);     this.transPage.set(1); this.loadTransactions(); }
  onTransChauf(e: Event):     void { this.transChauf.set((e.target as HTMLInputElement).value);     this.transPage.set(1); this.loadTransactions(); }
  onTransDateDebut(e: Event): void { this.transDateDebut.set((e.target as HTMLInputElement).value); this.transPage.set(1); this.loadTransactions(); }
  onTransDateFin(e: Event):   void { this.transDateFin.set((e.target as HTMLInputElement).value);   this.transPage.set(1); this.loadTransactions(); }
  onTransPage(p: number):     void { this.transPage.set(p); this.loadTransactions(); }

  isColVisible(key: string): boolean { return this.visibleColumns().includes(key); }
  toggleCol(key: string): void {
    const cols = this.visibleColumns();
    this.visibleColumns.set(cols.includes(key) ? cols.filter(c => c !== key) : [...cols, key]);
  }
  isNumericCol(key: string): boolean {
    return ['volume','montant','prix_unitaire','solde_avant','solde_apres',
            'montant_preautorise','kilometrage_precedent','kilometrage_actuel',
            'bonus_mypass_utilise'].includes(key);
  }
  statutClass(s: string): string {
    if (!s) return 'badge-gray';
    const l = s.toLowerCase();
    if (l.includes('reconcili') || l.includes('réconcili')) return 'badge-green';
    if (l.includes('annul')) return 'badge-danger';
    return 'badge-gray';
  }

  exportExcel(): void {
    if (this.exporting()) return;
    this.exporting.set(true);
    this.api.getTransactions({ ...this.buildTransFilters(), page: 1, page_size: 10000 }).subscribe({
      next: (res) => {
        const rows = res.results ?? [];
        this.exporting.set(false);
        const sep  = ';';
        const eol  = '\r\n';
        const esc  = (v: any) => { const s = String(v ?? '').replace(/"/g, '""'); return s.includes(sep)||s.includes('"')||s.includes('\n') ? `"${s}"` : s; };
        const hdrs = this.allColumns.map(c => c.label).join(sep);
        const data = rows.map((t: any) => this.allColumns.map(c => esc(t[c.key])).join(sep)).join(eol);
        const csv  = '\uFEFF' + hdrs + eol + data;
        this.downloadCsv(csv, `transactions_total_${new Date().toISOString().split('T')[0]}.csv`);
      },
      error: () => this.exporting.set(false),
    });
  }

  private downloadCsv(csv: string, filename: string): void {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ── Consommation ──
  onConsoInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut') this.consoDateDebut.set(val);
    if (field === 'fin')   this.consoDateFin.set(val);
    if (field === 'immat') this.consoImmat.set(val);
    if (field === 'chauf') this.consoNumChauf.set(val);
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
    if (this.consoImmat())    params['immatriculation']        = this.consoImmat();
    if (this.consoNumChauf()) params['numero_chauffeur_total'] = this.consoNumChauf();
    this.api.getConsommation(params).subscribe({
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
    const hdrs = ['Immatriculation','Km début','Km fin','Km parcourus',
                  'Volume (L)','Montant (FCFA)','Nb prises de carburant','Conso L/100km'].join(sep);
    const data = this.consoSorted().map(r =>
      [r.immatriculation, r.km_debut, r.km_fin, r.km_parcourus,
       r.volume_total, r.montant_total, r.nb_pleins, r.conso_100 ?? 'N/A'].join(sep)
    ).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data,
      `consommation_${this.consoDateDebut()}_${this.consoDateFin()}.csv`);
  }

  // ── Évolution agences ──
  onEvoInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut') this.evoDateDebut.set(val);
    if (field === 'fin')   this.evoDateFin.set(val);
    if (field === 'immat') this.evoImmat.set(val);
    if (field === 'chauf') this.evoNumChauf.set(val);
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
    if (this.evoImmat())    params['immatriculation']        = this.evoImmat();
    if (this.evoNumChauf()) params['numero_chauffeur_total'] = this.evoNumChauf();
    this.api.getEvolutionAgences(params).subscribe({
      next: (res) => { this.evoData.set(res.agences ?? []); this.evoLoading.set(false); setTimeout(() => this.renderChart(), 50); },
      error: (err) => { this.evoError.set(err?.error?.detail ?? 'Erreur.'); this.evoLoading.set(false); },
    });
  }

  renderChart(): void {
    const canvas   = this.chartCanvas?.nativeElement;
    if (!canvas) return;
    const agences  = this.evoData();
    const metrique = this.evoMetrique();
    if (!agences.length) return;
    const allMois  = Array.from(new Set(agences.flatMap(a => a.points.map(p => p.mois)))).sort();
    const datasets = agences.map((a, i) => {
      const map = new Map(a.points.map(p => [p.mois, p[metrique]]));
      return {
        label:           a.nom || a.client || 'Agence ?',
        data:            allMois.map(m => map.get(m) ?? 0),
        borderColor:     COLORS[i % COLORS.length],
        backgroundColor: COLORS[i % COLORS.length] + '22',
        borderWidth:     2.5, pointRadius: 4, pointHoverRadius: 6,
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
          }}}
        },
        scales: {
          x: { grid: { color: '#f0f0f0' }, ticks: { font: { size: 11 } } },
          y: { grid: { color: '#f0f0f0' }, title: { display: true, text: labels[metrique], font: { size: 11 } }, ticks: { font: { size: 11 } } }
        }
      }
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

  getColor(i: number): string { return COLORS[i % COLORS.length]; }

  sumPoints(points: AgencePoint[], key: 'volume' | 'montant' | 'nb'): number {
    return points.reduce((acc, p) => acc + (p[key] || 0), 0);
  }

  // ── Réconciliation ──
  onRecoInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    if (field === 'debut')     this.recoDateDebut.set(val);
    if (field === 'fin')       this.recoDateFin.set(val);
    if (field === 'immat')     this.recoImmat.set(val);
    if (field === 'chauf')     this.recoNumChauf.set(val);
    if (field === 'seuil_vol') this.recoSeuilVol.set(Number(val) || 5);
    if (field === 'seuil_mnt') this.recoSeuilMnt.set(Number(val) || 5);
  }

  lancerReconciliation(): void {
    if (!this.recoDateDebut() || !this.recoDateFin()) {
      this.recoError.set('Veuillez renseigner les deux dates.'); return;
    }
    this.recoLoading.set(true); this.recoError.set('');
    const params: Record<string, any> = {
      date_debut:   this.recoDateDebut(),
      date_fin:     this.recoDateFin(),
      seuil_volume: this.recoSeuilVol(),
      seuil_montant:this.recoSeuilMnt(),
    };
    if (this.recoImmat())    params['immatriculation']        = this.recoImmat();
    if (this.recoNumChauf()) params['numero_chauffeur_total'] = this.recoNumChauf();
    this.api.getReconciliation(params).subscribe({
      next: (res) => { this.recoData.set(res); this.recoLoading.set(false); },
      error: (err) => { this.recoError.set(err?.error?.detail ?? 'Erreur.'); this.recoLoading.set(false); },
    });
  }

  recoLignes(): any[] {
    const data   = this.recoData();
    if (!data) return [];
    const filtre = this.recoFiltre();
    return filtre ? data.lignes.filter((l: any) => l.statut === filtre) : data.lignes;
  }

  recoStatutClass(statut: string): string {
    const map: Record<string, string> = {
      reconcilie:    'badge-green',
      ecart_volume:  'badge-warning',
      ecart_montant: 'badge-warning',
      double_ecart:  'badge-danger',
      total_only:    'badge-navy',
      ubifleet_only: 'badge-gray',
    };
    return map[statut] ?? 'badge-gray';
  }

  recoStatutLabel(statut: string): string {
    const map: Record<string, string> = {
      reconcilie:    'Réconcilié',
      ecart_volume:  'Écart volume',
      ecart_montant: 'Écart montant',
      double_ecart:  'Double écart',
      total_only:    'Total seul.',
      ubifleet_only: 'UbiFleet seul.',
    };
    return map[statut] ?? statut;
  }

  exportRecoCsv(): void {
    const sep = ';'; const eol = '\r\n';
    const hdrs = [
      'Statut','Immatriculation','Date','Heure',
      'N° Ticket Total','Vol. Total (L)','Mnt. Total','Station','Produit','Chauf. Total','N° Chauf.',
      'N° Bon UbiFleet','Vol. UbiFleet (L)','Mnt. UbiFleet','Chauf. UbiFleet',
      'Écart Vol. (L)','Écart Mnt. (FCFA)','% Écart Vol.','% Écart Mnt.'
    ].join(sep);
    const data = this.recoLignes().map((l: any) => [
      this.recoStatutLabel(l.statut), l.immatriculation, l.date, l.heure ?? '',
      l.total_ticket ?? '', l.total_volume ?? '', l.total_montant ?? '',
      l.total_station ?? '', l.total_produit ?? '', l.total_chauffeur ?? '', l.total_num_chauf ?? '',
      l.ubi_bon ?? '', l.ubi_volume ?? '', l.ubi_montant ?? '', l.ubi_chauffeur ?? '',
      l.ecart_volume, l.ecart_montant, l.pct_volume, l.pct_montant,
    ].join(sep)).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data,
      `reconciliation_${this.recoDateDebut()}_${this.recoDateFin()}.csv`);
  }
}
