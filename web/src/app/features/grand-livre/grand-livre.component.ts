// UbiFleet — Grand Livre Comptable (Angular 18)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, computed,
  ElementRef, ViewChild
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpEventType } from '@angular/common/http';
import { GrandLivreApiService } from '../../core/services/api.service';

interface ImportResult {
  import_id: string; fichier: string;
  code_agence: string; libelle_agence: string;
  nb_lignes: number; importees: number; doublons: number; erreurs: number;
  lignes_erreur: { ligne: number; erreur: string; compte: string }[];
}
interface ImportHistorique {
  id: string; fichier_nom: string; date_import: string;
  nb_lignes: number; nb_importees: number; nb_doublons: number;
  nb_erreurs: number; importe_par_nom: string | null;
}
interface LigneGL {
  id: string; code_agence: string; libelle_agence: string;
  compte: string; libelle_compte: string;
  date_analytique: string; date_comptable: string;
  origine: string; piece: string; no_ligne: number; no_analytique: number;
  libelle_ecriture: string; debit: number; credit: number;
}
interface TotalRow {
  code_agence?: string; libelle_agence?: string;
  compte?: string; libelle_compte?: string;
  nb: number; debit: number; credit: number; solde: number;
}
interface StatsData {
  nb_lignes: number; total_debit: number; total_credit: number; solde: number;
  par_agence: TotalRow[]; par_compte: TotalRow[];
  par_agence_compte: TotalRow[]; par_origine: { origine: string; nb: number; debit: number; credit: number }[];
}

type Tab = 'import' | 'historique' | 'lignes' | 'totaux' | 'statistiques';

const CHART_COLORS = ['#092440','#5bd988','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16','#f97316','#ec4899'];

@Component({
  selector: 'ubi-grand-livre',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './grand-livre.component.html',
  styleUrls: ['./grand-livre.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GrandLivreComponent implements OnInit, OnDestroy {
  @ViewChild('chartDebCreCanvas') chartDebCreCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartAgenceCanvas') chartAgenceCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartOrigineCanvas') chartOrigineCanvas?: ElementRef<HTMLCanvasElement>;

  private api = inject(GrandLivreApiService);
  private charts: any[] = [];

  activeTab    = signal<Tab>('import');
  isDragOver   = signal(false);
  selectedFile = signal<File | null>(null);
  uploading    = signal(false);
  uploadPct    = signal(0);
  result       = signal<ImportResult | null>(null);
  importError  = signal('');

  historique     = signal<ImportHistorique[]>([]);
  historiqueLoad = signal(false);

  // ── Lignes ──
  lignes       = signal<LigneGL[]>([]);
  lignesTotal  = signal(0);
  lignesLoad   = signal(false);
  lignesPage   = signal(1);
  lignesSearch = signal('');
  lignesAgence = signal('');
  lignesCompte = signal('');
  lignesDebut  = signal('');
  lignesFin    = signal('');
  lignesOrigine= signal('');
  exporting    = signal(false);

  // ── Totaux ──
  totauxLoad      = signal(false);
  totauxData      = signal<StatsData | null>(null);
  totauxAgence    = signal('');
  totauxCompte    = signal('');
  totauxDebut     = signal('');
  totauxFin       = signal('');
  totauxOrigine   = signal('');
  totauxVue       = signal<'agence' | 'compte' | 'agence_compte'>('agence');
  totauxSortCol   = signal('debit');
  totauxSortAsc   = signal(false);

  // ── Statistiques ──
  statsLoad  = signal(false);
  statsData  = signal<StatsData | null>(null);
  statsAgence= signal('');
  statsDebut = signal('');
  statsFin   = signal('');

  // ── Computed ──
  get lignesPages(): number { return Math.ceil(this.lignesTotal() / 20) || 1; }
  get lignesPagesArr(): number[] {
    const cur = this.lignesPage(), max = this.lignesPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  totauxRows = computed((): TotalRow[] => {
    const d = this.totauxData();
    if (!d) return [];
    const vue = this.totauxVue();
    let rows: TotalRow[] = vue === 'agence' ? d.par_agence
      : vue === 'compte' ? d.par_compte
      : d.par_agence_compte;
    const col = this.totauxSortCol();
    const asc = this.totauxSortAsc();
    return [...rows].sort((a, b) => {
      const va = (a as any)[col] ?? 0;
      const vb = (b as any)[col] ?? 0;
      return typeof va === 'string'
        ? asc ? va.localeCompare(vb) : vb.localeCompare(va)
        : asc ? va - vb : vb - va;
    });
  });

  ngOnInit(): void { this.loadHistorique(); }

  ngOnDestroy(): void {
    this.charts.forEach(c => { try { c.destroy(); } catch (_) {} });
    this.charts = [];
  }

  onTabChange(tab: Tab): void {
    this.activeTab.set(tab);
    if (tab === 'lignes'       && this.lignes().length === 0) this.loadLignes();
    if (tab === 'historique')  this.loadHistorique();
    if (tab === 'totaux'       && !this.totauxData())  this.loadTotaux();
    if (tab === 'statistiques' && !this.statsData())   this.loadStats();
  }

  // ── Drag & Drop ──
  onDragOver(e: DragEvent): void { e.preventDefault(); this.isDragOver.set(true); }
  onDragLeave(): void             { this.isDragOver.set(false); }
  onDrop(e: DragEvent): void {
    e.preventDefault(); this.isDragOver.set(false);
    const f = e.dataTransfer?.files;
    if (f && f.length > 0) this.setFile(f[0]);
  }
  onFileInput(e: Event): void {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) this.setFile(input.files[0]);
  }
  setFile(file: File): void {
    const ext = file.name.toLowerCase();
    if (!ext.endsWith('.xls') && !ext.endsWith('.xlsx') && !ext.endsWith('.csv')) {
      this.importError.set('Format non supporté. Utilisez XLS, XLSX ou CSV.'); return;
    }
    this.selectedFile.set(file); this.result.set(null); this.importError.set('');
  }
  clearFile(): void { this.selectedFile.set(null); this.result.set(null); this.importError.set(''); }
  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' Ko';
    return (bytes/(1024*1024)).toFixed(2) + ' Mo';
  }

  // ── Import ──
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
      error: (err) => { this.uploading.set(false); this.importError.set(err?.error?.detail ?? "Erreur."); },
    });
  }

  loadHistorique(): void {
    this.historiqueLoad.set(true);
    this.api.getHistorique({ page_size: 50 }).subscribe({
      next: (res) => { this.historique.set(res.results ?? []); this.historiqueLoad.set(false); },
      error: () => this.historiqueLoad.set(false),
    });
  }

  // ── Lignes ──
  buildLignesFilters(): Record<string, any> {
    const f: Record<string, any> = { page: this.lignesPage(), page_size: 20 };
    if (this.lignesSearch())  f['search']          = this.lignesSearch();
    if (this.lignesAgence())  f['code_agence']     = this.lignesAgence();
    if (this.lignesCompte())  f['compte']          = this.lignesCompte();
    if (this.lignesDebut())   f['date_analytique'] = this.lignesDebut();
    if (this.lignesFin())     f['date_comptable']  = this.lignesFin();
    if (this.lignesOrigine()) f['origine']         = this.lignesOrigine();
    return f;
  }
  loadLignes(): void {
    this.lignesLoad.set(true);
    this.api.getLignes(this.buildLignesFilters()).subscribe({
      next: (res) => { this.lignes.set(res.results ?? []); this.lignesTotal.set(res.count ?? 0); this.lignesLoad.set(false); },
      error: () => this.lignesLoad.set(false),
    });
  }
  onLignes(field: string, e: Event): void {
    const v = (e.target as HTMLInputElement).value;
    if (field === 'search')   this.lignesSearch.set(v);
    if (field === 'agence')   this.lignesAgence.set(v);
    if (field === 'compte')   this.lignesCompte.set(v);
    if (field === 'debut')    this.lignesDebut.set(v);
    if (field === 'fin')      this.lignesFin.set(v);
    if (field === 'origine')  this.lignesOrigine.set(v);
    this.lignesPage.set(1); this.loadLignes();
  }
  onLignesPage(p: number): void { this.lignesPage.set(p); this.loadLignes(); }

  exportCsv(): void {
    if (this.exporting()) return;
    this.exporting.set(true);
    this.api.getLignes({ ...this.buildLignesFilters(), page: 1, page_size: 10000 }).subscribe({
      next: (res) => {
        const rows = (res.results ?? []) as LigneGL[];
        this.exporting.set(false);
        const sep = ';'; const eol = '\r\n';
        const hdrs = ['Code agence','Libellé agence','Compte','Libellé compte',
          'Date analytique','Date comptable','Origine','Pièce',
          'N° ligne','N° analytique','Libellé écriture','Débit','Crédit'].join(sep);
        const data = rows.map(r => [
          r.code_agence, r.libelle_agence, r.compte, r.libelle_compte,
          r.date_analytique ?? '', r.date_comptable ?? '',
          r.origine, r.piece, r.no_ligne, r.no_analytique,
          r.libelle_ecriture, r.debit, r.credit
        ].join(sep)).join(eol);
        this.downloadCsv('\uFEFF' + hdrs + eol + data,
          `grand_livre_${new Date().toISOString().split('T')[0]}.csv`);
      },
      error: () => this.exporting.set(false),
    });
  }

  // ── Totaux ──
  buildTotauxFilters(): Record<string, any> {
    const f: Record<string, any> = {};
    if (this.totauxAgence())  f['code_agence']     = this.totauxAgence();
    if (this.totauxCompte())  f['compte']          = this.totauxCompte();
    if (this.totauxDebut())   f['date_analytique'] = this.totauxDebut();
    if (this.totauxFin())     f['date_comptable']  = this.totauxFin();
    if (this.totauxOrigine()) f['origine']         = this.totauxOrigine();
    return f;
  }
  loadTotaux(): void {
    this.totauxLoad.set(true);
    this.api.getTotaux(this.buildTotauxFilters()).subscribe({
      next: (res) => { this.totauxData.set(res); this.totauxLoad.set(false); },
      error: () => this.totauxLoad.set(false),
    });
  }
  onTotaux(field: string, e: Event): void {
    const v = (e.target as HTMLInputElement).value;
    if (field === 'agence')  this.totauxAgence.set(v);
    if (field === 'compte')  this.totauxCompte.set(v);
    if (field === 'debut')   this.totauxDebut.set(v);
    if (field === 'fin')     this.totauxFin.set(v);
    if (field === 'origine') this.totauxOrigine.set(v);
    this.loadTotaux();
  }
  sortTotaux(col: string): void {
    if (this.totauxSortCol() === col) this.totauxSortAsc.set(!this.totauxSortAsc());
    else { this.totauxSortCol.set(col); this.totauxSortAsc.set(false); }
  }
  exportTotauxCsv(): void {
    const rows = this.totauxRows();
    const vue  = this.totauxVue();
    const sep  = ';'; const eol = '\r\n';
    const hdrs = vue === 'agence_compte'
      ? ['Code agence','Libellé agence','Compte','Libellé compte','Nb écritures','Débit','Crédit','Solde'].join(sep)
      : vue === 'agence'
        ? ['Code agence','Libellé agence','Nb écritures','Débit','Crédit','Solde'].join(sep)
        : ['Compte','Libellé compte','Nb écritures','Débit','Crédit','Solde'].join(sep);
    const data = rows.map(r => {
      const base = [r.nb, r.debit, r.credit, r.solde];
      if (vue === 'agence_compte') return [r.code_agence, r.libelle_agence, r.compte, r.libelle_compte, ...base].join(sep);
      if (vue === 'agence') return [r.code_agence, r.libelle_agence, ...base].join(sep);
      return [r.compte, r.libelle_compte, ...base].join(sep);
    }).join(eol);
    this.downloadCsv('\uFEFF' + hdrs + eol + data, `totaux_${vue}_${new Date().toISOString().split('T')[0]}.csv`);
  }

  // ── Statistiques ──
  buildStatsFilters(): Record<string, any> {
    const f: Record<string, any> = {};
    if (this.statsAgence()) f['code_agence']     = this.statsAgence();
    if (this.statsDebut())  f['date_analytique'] = this.statsDebut();
    if (this.statsFin())    f['date_comptable']  = this.statsFin();
    return f;
  }
  loadStats(): void {
    this.statsLoad.set(true);
    this.api.getStats(this.buildStatsFilters()).subscribe({
      next: (res) => {
        this.statsData.set(res);
        this.statsLoad.set(false);
        setTimeout(() => this.renderCharts(), 80);
      },
      error: () => this.statsLoad.set(false),
    });
  }
  onStats(field: string, e: Event): void {
    const v = (e.target as HTMLInputElement).value;
    if (field === 'agence') this.statsAgence.set(v);
    if (field === 'debut')  this.statsDebut.set(v);
    if (field === 'fin')    this.statsFin.set(v);
    this.loadStats();
  }

  renderCharts(): void {
    const d = this.statsData();
    if (!d) return;
    this.charts.forEach(c => { try { c.destroy(); } catch (_) {} });
    this.charts = [];
    const Chart = (window as any)['Chart'];
    if (!Chart) { this.loadChartJs(() => this.renderCharts()); return; }

    // 1. Débit / Crédit par agence (barres groupées)
    if (this.chartDebCreCanvas?.nativeElement) {
      const labels = d.par_agence.map((a: TotalRow) => a.code_agence ?? '');
      this.charts.push(new Chart(this.chartDebCreCanvas.nativeElement, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { label: 'Débit', data: d.par_agence.map((a: TotalRow) => a.debit), backgroundColor: '#092440cc', borderRadius: 4 },
            { label: 'Crédit', data: d.par_agence.map((a: TotalRow) => a.credit), backgroundColor: '#5bd98899', borderRadius: 4 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'top' }, title: { display: true, text: 'Débit / Crédit par agence' } },
          scales: { y: { ticks: { callback: (v: number) => v.toLocaleString('fr-FR') + ' FCFA' } } },
        },
      }));
    }

    // 2. Répartition des débits par agence (camembert)
    if (this.chartAgenceCanvas?.nativeElement) {
      const agences = d.par_agence.filter((a: TotalRow) => a.debit > 0);
      this.charts.push(new Chart(this.chartAgenceCanvas.nativeElement, {
        type: 'doughnut',
        data: {
          labels: agences.map((a: TotalRow) => `${a.code_agence} — ${a.libelle_agence}`),
          datasets: [{
            data: agences.map((a: TotalRow) => a.debit),
            backgroundColor: CHART_COLORS.slice(0, agences.length),
            borderWidth: 2, borderColor: '#fff',
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { font: { size: 11 } } },
            title: { display: true, text: 'Répartition des débits par agence' },
            tooltip: { callbacks: { label: (ctx: any) => {
              const v = ctx.parsed;
              const total = ctx.dataset.data.reduce((a: number, b: number) => a + b, 0);
              return ` ${v.toLocaleString('fr-FR')} FCFA (${((v/total)*100).toFixed(1)}%)`;
            }}},
          },
        },
      }));
    }

    // 3. Top 10 comptes par débit (colonnes horizontales)
    if (this.chartOrigineCanvas?.nativeElement) {
      const top10 = [...d.par_compte].sort((a: TotalRow, b: TotalRow) => b.debit - a.debit).slice(0, 10);
      this.charts.push(new Chart(this.chartOrigineCanvas.nativeElement, {
        type: 'bar',
        data: {
          labels: top10.map((c: TotalRow) => c.compte),
          datasets: [
            { label: 'Débit', data: top10.map((c: TotalRow) => c.debit), backgroundColor: '#3b82f6cc', borderRadius: 4 },
            { label: 'Crédit', data: top10.map((c: TotalRow) => c.credit), backgroundColor: '#f59e0bcc', borderRadius: 4 },
          ],
        },
        options: {
          indexAxis: 'y',
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'top' }, title: { display: true, text: 'Top 10 comptes par débit' } },
          scales: { x: { ticks: { callback: (v: number) => v.toLocaleString('fr-FR') } } },
        },
      }));
    }
  }

  loadChartJs(cb: () => void): void {
    if ((window as any)['Chart']) { cb(); return; }
    // Chart.js chargé à la demande depuis l'application (pas de CDN)
    import('chart.js/auto').then(m => { (window as any)['Chart'] = m.default; cb(); });
  }

  getColor(i: number): string { return CHART_COLORS[i % CHART_COLORS.length]; }

  private downloadCsv(csv: string, filename: string): void {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click();
    URL.revokeObjectURL(a.href);
  }
}
