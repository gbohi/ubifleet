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
import { AuthService } from '../../core/services/auth.service';
import { messageErreurApi } from '../../core/services/fenetre-saisie.service';

interface ImportResult {
  import_id: string; fichier: string;
  code_agence: string; libelle_agence: string;
  nb_lignes: number; importees: number; doublons: number; erreurs: number;
  lignes_erreur: { ligne: number; erreur: string; compte: string }[];
}
interface ImportHistorique {
  id: string; fichier_nom: string; date_import: string;
  code_agence: string; libelle_agence: string;
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
  par_agence: TotalRow[]; par_compte: TotalRow[]; par_agence_compte: TotalRow[];
  par_origine: { origine: string; nb: number; debit: number; credit: number }[];
  par_mois: { mois: string; nb: number; debit: number; credit: number; solde: number }[];
}
interface OptionsGL {
  agences: { code_agence: string; libelle_agence: string }[];
  origines: string[];
  date_debut: string | null; date_fin: string | null; nb_lignes: number;
}
interface FiltresGL {
  date_debut: string; date_fin: string; code_agence: string;
  compte: string; origine: string; search: string;
}

type Tab = 'lignes' | 'totaux' | 'statistiques' | 'imports';

const FILTRES_VIDES: FiltresGL = { date_debut: '', date_fin: '', code_agence: '', compte: '', origine: '', search: '' };
const CHART_COLORS = ['#092440','#5bd988','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16','#f97316','#ec4899'];
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const PAGE = 25;

@Component({
  selector: 'ubi-grand-livre',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './grand-livre.component.html',
  styleUrls: ['./grand-livre.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GrandLivreComponent implements OnInit, OnDestroy {
  @ViewChild('chartMoisCanvas') chartMoisCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartAgenceCanvas') chartAgenceCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('chartComptesCanvas') chartComptesCanvas?: ElementRef<HTMLCanvasElement>;

  private api = inject(GrandLivreApiService);
  private auth = inject(AuthService);
  private charts: any[] = [];
  private minuterie?: ReturnType<typeof setTimeout>;

  /** Import et suppression d'import : utilisateurs « Toutes les agences ». */
  readonly toutesAgences = !this.auth.currentUser()?.agence;

  activeTab = signal<Tab>('lignes');
  options   = signal<OptionsGL | null>(null);
  filtres   = signal<FiltresGL>({ ...FILTRES_VIDES });
  nbFiltresActifs = computed(() => Object.values(this.filtres()).filter(v => !!v).length);
  plusieursAgences = computed(() => (this.options()?.agences.length ?? 0) > 1);

  // ── Import ──
  isDragOver   = signal(false);
  selectedFile = signal<File | null>(null);
  uploading    = signal(false);
  uploadPct    = signal(0);
  result       = signal<ImportResult | null>(null);
  importError  = signal('');

  historique     = signal<ImportHistorique[]>([]);
  historiqueLoad = signal(false);
  suppression    = signal<ImportHistorique | null>(null);
  suppressionMsg = signal('');
  suppressionEnCours = signal(false);

  // ── Écritures ──
  lignes      = signal<LigneGL[]>([]);
  lignesTotal = signal(0);
  lignesLoad  = signal(false);
  lignesPage  = signal(1);
  lignesTri   = signal('');
  exporting   = signal(false);
  private lignesAJour = false;

  // ── Totaux & statistiques (même calcul serveur) ──
  statsLoad = signal(false);
  statsData = signal<StatsData | null>(null);
  totauxVue     = signal<'agence' | 'compte' | 'agence_compte'>('compte');
  totauxSortCol = signal('compte');
  totauxSortAsc = signal(true);
  private statsAJour = false;

  lignesPages = computed(() => Math.ceil(this.lignesTotal() / PAGE) || 1);
  lignesPagesArr = computed(() => {
    const cur = this.lignesPage(), max = this.lignesPages();
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  });

  totauxRows = computed((): TotalRow[] => {
    const d = this.statsData();
    if (!d) return [];
    const vue = this.totauxVue();
    const rows = vue === 'agence' ? d.par_agence : vue === 'compte' ? d.par_compte : d.par_agence_compte;
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

  ngOnInit(): void {
    this.chargerOptions(true);
  }

  ngOnDestroy(): void {
    clearTimeout(this.minuterie);
    this.detruireGraphiques();
  }

  private chargerOptions(premierChargement = false): void {
    this.api.getOptions().subscribe({
      next: (o: OptionsGL) => {
        this.options.set(o);
        if (premierChargement) {
          // Aucun grand livre encore importé : on commence par l'import.
          this.onTabChange(o.nb_lignes === 0 && this.toutesAgences ? 'imports' : 'lignes');
        }
      },
      error: () => premierChargement && this.onTabChange('lignes'),
    });
  }

  onTabChange(tab: Tab): void {
    this.activeTab.set(tab);
    this.chargerOngletActif();
  }

  private chargerOngletActif(): void {
    const tab = this.activeTab();
    if (tab === 'lignes' && !this.lignesAJour) this.loadLignes();
    if ((tab === 'totaux' || tab === 'statistiques') && !this.statsAJour) this.loadStats();
    if (tab === 'statistiques' && this.statsAJour) setTimeout(() => this.renderCharts(), 50);
    if (tab === 'imports') this.loadHistorique();
  }

  /** Les données affichées ne correspondent plus (filtres ou import modifiés). */
  private invalider(): void {
    this.lignesAJour = false;
    this.statsAJour = false;
    this.lignesPage.set(1);
    this.chargerOngletActif();
  }

  // ── Filtres (communs aux écritures, totaux et statistiques) ──
  appliquerFiltre(champ: keyof FiltresGL, valeur: string): void {
    this.filtres.update(f => ({ ...f, [champ]: valeur.trim() }));
    this.invalider();
  }
  /** Saisie libre (compte, recherche) : appliquée après une courte pause. */
  saisirFiltre(champ: keyof FiltresGL, valeur: string): void {
    clearTimeout(this.minuterie);
    this.minuterie = setTimeout(() => this.appliquerFiltre(champ, valeur), 350);
  }
  reinitialiserFiltres(): void {
    clearTimeout(this.minuterie);
    this.filtres.set({ ...FILTRES_VIDES });
    this.invalider();
  }
  private paramsFiltres(): Record<string, any> {
    const f: Record<string, any> = {};
    Object.entries(this.filtres()).forEach(([k, v]) => { if (v) f[k] = v; });
    return f;
  }
  libelleAgence(code: string): string {
    const a = this.options()?.agences.find(x => x.code_agence === code);
    return a?.libelle_agence ? `${code} — ${a.libelle_agence}` : code;
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
    input.value = '';
  }
  setFile(file: File): void {
    const ext = file.name.toLowerCase();
    if (!ext.endsWith('.xls') && !ext.endsWith('.xlsx') && !ext.endsWith('.csv')) {
      this.importError.set('Format non supporté. Utilisez XLS, XLSX ou CSV.'); return;
    }
    if (file.size > 20 * 1024 * 1024) {
      this.importError.set('Fichier trop volumineux (20 Mo maximum).'); return;
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
          this.selectedFile.set(null);
          this.apresChangementDonnees();
        }
      },
      error: (err) => { this.uploading.set(false); this.importError.set(messageErreurApi(err, "L'import a échoué.")); },
    });
  }

  voirEcrituresImport(): void {
    this.result.set(null);
    this.onTabChange('lignes');
  }

  private apresChangementDonnees(): void {
    this.chargerOptions();
    this.lignesAJour = false;
    this.statsAJour = false;
    this.loadHistorique();
  }

  loadHistorique(): void {
    this.historiqueLoad.set(true);
    this.api.getHistorique({ page_size: 100 }).subscribe({
      next: (res) => { this.historique.set(res.results ?? []); this.historiqueLoad.set(false); },
      error: () => this.historiqueLoad.set(false),
    });
  }

  demanderSuppression(h: ImportHistorique): void { this.suppressionMsg.set(''); this.suppression.set(h); }
  confirmerSuppression(): void {
    const h = this.suppression();
    if (!h || this.suppressionEnCours()) return;
    this.suppressionEnCours.set(true);
    this.api.supprimerImport(h.id).subscribe({
      next: () => {
        this.suppressionEnCours.set(false);
        this.suppression.set(null);
        this.suppressionMsg.set(`Import « ${h.fichier_nom} » supprimé avec ses ${h.nb_importees} écriture(s).`);
        this.apresChangementDonnees();
      },
      error: err => {
        this.suppressionEnCours.set(false);
        this.suppressionMsg.set(messageErreurApi(err, 'Suppression impossible.'));
      },
    });
  }

  // ── Écritures ──
  loadLignes(): void {
    this.lignesLoad.set(true);
    this.lignesAJour = true;
    const params: Record<string, any> = { ...this.paramsFiltres(), page: this.lignesPage(), page_size: PAGE };
    if (this.lignesTri()) params['ordering'] = this.lignesTri();
    this.api.getLignes(params).subscribe({
      next: (res) => { this.lignes.set(res.results ?? []); this.lignesTotal.set(res.count ?? 0); this.lignesLoad.set(false); },
      error: () => { this.lignesLoad.set(false); this.lignesAJour = false; },
    });
  }
  onLignesPage(p: number): void { this.lignesPage.set(p); this.loadLignes(); }
  trierLignes(col: string): void {
    const t = this.lignesTri();
    this.lignesTri.set(t === col ? '-' + col : t === '-' + col ? '' : col);
    this.lignesPage.set(1);
    this.loadLignes();
  }
  iconeTri(col: string): string {
    const t = this.lignesTri();
    return t === col ? 'fa-sort-up' : t === '-' + col ? 'fa-sort-down' : 'fa-sort';
  }

  /** Export de toutes les écritures filtrées (pages de 1000). */
  exportCsv(): void {
    if (this.exporting()) return;
    this.exporting.set(true);
    const toutes: LigneGL[] = [];
    const page = (n: number) => {
      this.api.getLignes({ ...this.paramsFiltres(), page: n, page_size: 1000 }).subscribe({
        next: (res) => {
          toutes.push(...(res.results ?? []));
          if (res.next) { page(n + 1); return; }
          this.exporting.set(false);
          const hdrs = ['Code agence','Libellé agence','Compte','Libellé compte',
            'Date analytique','Date comptable','Origine','Pièce',
            'N° ligne','N° analytique','Libellé écriture','Débit','Crédit'];
          const data = toutes.map(r => [
            r.code_agence, r.libelle_agence, r.compte, r.libelle_compte,
            r.date_analytique ?? '', r.date_comptable ?? '',
            r.origine, r.piece, r.no_ligne ?? '', r.no_analytique ?? '',
            r.libelle_ecriture, this.montantCsv(r.debit), this.montantCsv(r.credit),
          ]);
          this.downloadCsv([hdrs, ...data], `grand_livre_${new Date().toISOString().split('T')[0]}.csv`);
        },
        error: () => this.exporting.set(false),
      });
    };
    page(1);
  }

  // ── Totaux / statistiques ──
  loadStats(): void {
    this.statsLoad.set(true);
    this.statsAJour = true;
    this.api.getStats(this.paramsFiltres()).subscribe({
      next: (res) => {
        this.statsData.set(res);
        this.statsLoad.set(false);
        if (this.activeTab() === 'statistiques') setTimeout(() => this.renderCharts(), 50);
      },
      error: () => { this.statsLoad.set(false); this.statsAJour = false; },
    });
  }
  changerVue(vue: 'agence' | 'compte' | 'agence_compte'): void {
    this.totauxVue.set(vue);
    this.totauxSortCol.set(vue === 'agence' ? 'code_agence' : 'compte');
    this.totauxSortAsc.set(true);
  }
  sortTotaux(col: string): void {
    if (this.totauxSortCol() === col) this.totauxSortAsc.set(!this.totauxSortAsc());
    else { this.totauxSortCol.set(col); this.totauxSortAsc.set(typeof col === 'string' && ['code_agence', 'compte'].includes(col)); }
  }
  iconeTriTotaux(col: string): string {
    if (this.totauxSortCol() !== col) return 'fa-sort';
    return this.totauxSortAsc() ? 'fa-sort-up' : 'fa-sort-down';
  }
  /** Clic sur une ligne des totaux : affiche ses écritures. */
  voirEcritures(r: TotalRow): void {
    this.filtres.update(f => ({
      ...f,
      ...(r.compte ? { compte: r.compte } : {}),
      ...(r.code_agence ? { code_agence: r.code_agence } : {}),
    }));
    this.lignesAJour = false;
    this.statsAJour = false;
    this.lignesPage.set(1);
    this.onTabChange('lignes');
  }
  exportTotauxCsv(): void {
    const rows = this.totauxRows();
    const vue  = this.totauxVue();
    const base = ['Nb écritures','Débit','Crédit','Solde'];
    const hdrs = vue === 'agence_compte' ? ['Code agence','Libellé agence','Compte','Libellé compte', ...base]
      : vue === 'agence' ? ['Code agence','Libellé agence', ...base]
      : ['Compte','Libellé compte', ...base];
    const data = rows.map(r => {
      const m = [r.nb, this.montantCsv(r.debit), this.montantCsv(r.credit), this.montantCsv(r.solde)];
      if (vue === 'agence_compte') return [r.code_agence, r.libelle_agence, r.compte, r.libelle_compte, ...m];
      if (vue === 'agence') return [r.code_agence, r.libelle_agence, ...m];
      return [r.compte, r.libelle_compte, ...m];
    });
    this.downloadCsv([hdrs, ...data], `totaux_${vue}_${new Date().toISOString().split('T')[0]}.csv`);
  }

  // ── Graphiques ──
  private detruireGraphiques(): void {
    this.charts.forEach(c => { try { c.destroy(); } catch (_) {} });
    this.charts = [];
  }

  renderCharts(): void {
    const d = this.statsData();
    if (!d || this.activeTab() !== 'statistiques') return;
    const Chart = (window as any)['Chart'];
    if (!Chart) { this.loadChartJs(() => this.renderCharts()); return; }
    this.detruireGraphiques();
    const fcfa = (v: number) => Math.round(v).toLocaleString('fr-FR');

    // 1. Évolution mensuelle débit / crédit
    if (this.chartMoisCanvas?.nativeElement && d.par_mois.length) {
      this.charts.push(new Chart(this.chartMoisCanvas.nativeElement, {
        type: 'bar',
        data: {
          labels: d.par_mois.map(m => { const [a, mo] = m.mois.split('-'); return `${MOIS[+mo - 1]} ${a}`; }),
          datasets: [
            { label: 'Débit', data: d.par_mois.map(m => m.debit), backgroundColor: '#092440cc', borderRadius: 4 },
            { label: 'Crédit', data: d.par_mois.map(m => m.credit), backgroundColor: '#ef4444aa', borderRadius: 4 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'top' },
                     tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.dataset.label} : ${fcfa(ctx.parsed.y)} FCFA` } } },
          scales: { y: { ticks: { callback: (v: number) => fcfa(v) } } },
        },
      }));
    }

    // 2. Répartition des débits par agence (si plusieurs agences)
    if (this.chartAgenceCanvas?.nativeElement) {
      const agences = d.par_agence.filter(a => a.debit > 0);
      this.charts.push(new Chart(this.chartAgenceCanvas.nativeElement, {
        type: 'doughnut',
        data: {
          labels: agences.map(a => `${a.code_agence} — ${a.libelle_agence}`),
          datasets: [{
            data: agences.map(a => a.debit),
            backgroundColor: CHART_COLORS.slice(0, agences.length),
            borderWidth: 2, borderColor: '#fff',
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { font: { size: 11 } } },
            tooltip: { callbacks: { label: (ctx: any) => {
              const v = ctx.parsed;
              const total = ctx.dataset.data.reduce((a: number, b: number) => a + b, 0);
              return ` ${fcfa(v)} FCFA (${((v/total)*100).toFixed(1)} %)`;
            }}},
          },
        },
      }));
    }

    // 3. Top 10 comptes par débit
    if (this.chartComptesCanvas?.nativeElement) {
      const top10 = [...d.par_compte].sort((a, b) => b.debit - a.debit).slice(0, 10);
      this.charts.push(new Chart(this.chartComptesCanvas.nativeElement, {
        type: 'bar',
        data: {
          labels: top10.map(c => `${c.compte} ${c.libelle_compte ?? ''}`.slice(0, 40)),
          datasets: [
            { label: 'Débit', data: top10.map(c => c.debit), backgroundColor: '#3b82f6cc', borderRadius: 4 },
            { label: 'Crédit', data: top10.map(c => c.credit), backgroundColor: '#f59e0bcc', borderRadius: 4 },
          ],
        },
        options: {
          indexAxis: 'y',
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'top' },
                     tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.dataset.label} : ${fcfa(ctx.parsed.x)} FCFA` } } },
          scales: { x: { ticks: { callback: (v: number) => fcfa(v) } } },
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

  private montantCsv(v: number | null | undefined): string {
    return (Number(v) || 0).toFixed(2).replace('.', ',');
  }

  private downloadCsv(lignes: any[][], filename: string): void {
    const cell = (v: any) => {
      const s = String(v ?? '');
      return /[;"\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = '﻿' + lignes.map(l => l.map(cell).join(';')).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click();
    URL.revokeObjectURL(a.href);
  }
}
