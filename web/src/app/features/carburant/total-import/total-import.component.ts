// UbiFleet — Transactions Total Carburant (Angular 18)
import {
  Component, inject, OnInit, ChangeDetectionStrategy, signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpEventType } from '@angular/common/http';
import { AgenceApiService, TotalImportApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';

interface ImportResult {
  import_id: string; fichier: string; nb_lignes: number;
  importees: number; doublons: number; erreurs: number;
  lignes_erreur: { ligne: number; erreur: string; immatriculation: string }[];
  colonnes_ignorees?: string[];
}
interface StatsTotal {
  nb_transactions: number; nb_effectives: number; volume: number; montant: number;
  nb_annulations: number; nb_annulees: number; periode: { debut: string | null; fin: string | null };
  plaques_inconnues: { immatriculation: string; nb: number; volume: number }[];
}
interface ImportHistorique {
  id: string; fichier_nom: string; date_import: string;
  nb_lignes: number; nb_importees: number; nb_doublons: number;
  nb_erreurs: number; importe_par_nom: string | null;
}
type Tab = 'import' | 'historique' | 'transactions';

@Component({
  selector: 'ubi-total-import',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, SelectRechercheComponent],
  templateUrl: './total-import.component.html',
  styleUrls: ['./total-import.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TotalImportComponent implements OnInit {
  private api = inject(TotalImportApiService);
  private agenceApi = inject(AgenceApiService);
  private auth = inject(AuthService);
  /** Import et suppression d'import : utilisateurs « Toutes les agences ». */
  readonly toutesAgences = !this.auth.currentUser()?.agence;

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
  transAgence       = signal('');
  transAnnulations  = signal<'' | 'masquer' | 'seulement'>('masquer');
  agences           = signal<{ id: string; nom: string }[]>([]);
  stats             = signal<StatsTotal | null>(null);
  showInconnues     = signal(false);
  suppression       = signal<ImportHistorique | null>(null);
  suppressionMsg    = signal('');
  plaquesFiltre     = signal<OptionRecherche[]>([]);
  chauffeursFiltre  = signal<OptionRecherche[]>([]);
  exporting         = signal(false);
  showColPicker     = signal(false);

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

  get totalPages(): number { return Math.ceil(this.transactionsTotal() / 20) || 1; }
  get pages(): number[] {
    const cur = this.transPage(), max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.loadHistorique();
    this.loadStats();
    if (this.toutesAgences) {
      this.agenceApi.getAll().subscribe({
        next: (l: any) => this.agences.set((Array.isArray(l) ? l : (l.results ?? [])).map((a: any) => ({ id: a.id, nom: a.nom }))),
        error: () => {},
      });
    }
    // Listes avec recherche : plaques et chauffeurs présents dans les transactions
    this.api.getValeursFiltres().subscribe({
      next: v => {
        this.plaquesFiltre.set(v.immatriculations.map(p => ({ value: p, label: p })));
        this.chauffeursFiltre.set(v.chauffeurs.map(c => ({ value: c.numero || c.nom, label: [c.numero, c.nom].filter(Boolean).join(' — ') })));
      },
      error: () => {},
    });
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
    if (ext.endsWith('.xls')) {
      this.importError.set("Ancien format Excel (.xls) : enregistrez le fichier en .xlsx ou en .csv depuis Excel.");
      return;
    }
    if (!ext.endsWith('.csv') && !ext.endsWith('.xlsx')) {
      this.importError.set('Format non supporté. Utilisez CSV ou Excel (.xlsx).');
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
          this.selectedFile.set(null); this.loadHistorique(); this.loadStats(); this.transactions.set([]);
        }
      },
      error: (err) => { this.uploading.set(false); this.importError.set(messageErreurApi(err, "Erreur lors de l'import.")); },
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
    if (this.transChauf())     f['numero_chauffeur'] = this.transChauf();
    if (this.transDateDebut()) f['date_debut']       = this.transDateDebut();
    if (this.transDateFin())   f['date_fin']         = this.transDateFin();
    if (this.transAgence())    f['agence']           = this.transAgence();
    if (this.transAnnulations()) f['annulations']    = this.transAnnulations();
    return f;
  }

  /** Synthèse des transactions filtrées (ventes effectives, annulations, plaques inconnues). */
  loadStats(): void {
    const { page, page_size, ...filtres } = this.buildTransFilters();
    delete filtres['annulations'];   // la synthèse distingue elle-même les annulations
    const n = ++this.requeteStats;
    this.api.getStats(filtres).subscribe({
      next: s => { if (n === this.requeteStats) this.stats.set(s); },
      error: () => {},
    });
  }
  private requeteStats = 0;

  private rechargerTransactions(): void {
    this.transPage.set(1);
    this.loadTransactions();
    this.loadStats();
  }
  onTransAgence(e: Event): void { this.transAgence.set((e.target as HTMLSelectElement).value); this.rechargerTransactions(); }
  onTransAnnulations(e: Event): void { this.transAnnulations.set((e.target as HTMLSelectElement).value as any); this.rechargerTransactions(); }
  reinitialiserFiltres(): void {
    this.transSearch.set(''); this.transImmat.set(''); this.transChauf.set('');
    this.transDateDebut.set(''); this.transDateFin.set(''); this.transAgence.set(''); this.transAnnulations.set('masquer');
    this.rechargerTransactions();
  }
  filtrerPlaque(p: string): void { this.showInconnues.set(false); this.onTransImmat(p); }

  // ── Suppression d'un import ──
  demanderSuppression(h: ImportHistorique): void { this.suppressionMsg.set(''); this.suppression.set(h); }
  confirmerSuppression(): void {
    const h = this.suppression();
    if (!h) return;
    this.api.deleteImport(h.id).subscribe({
      next: (r: any) => {
        this.suppression.set(null);
        this.suppressionMsg.set(r?.detail ?? 'Import supprimé.');
        this.loadHistorique(); this.loadStats(); this.transactions.set([]);
      },
      error: err => this.suppressionMsg.set(messageErreurApi(err, 'Suppression impossible.')),
    });
  }

  loadTransactions(): void {
    this.transactionsLoad.set(true);
    const n = ++this.requeteTransactions;   // seule la dernière demande s'affiche
    this.api.getTransactions(this.buildTransFilters()).subscribe({
      next: (res) => {
        if (n !== this.requeteTransactions) return;
        this.transactions.set(res.results ?? []);
        this.transactionsTotal.set(res.count ?? 0);
        this.transactionsLoad.set(false);
      },
      error: () => { if (n === this.requeteTransactions) this.transactionsLoad.set(false); },
    });
  }
  private requeteTransactions = 0;

  onTransSearch(e: Event):    void { this.transSearch.set((e.target as HTMLInputElement).value);    this.rechargerTransactions(); }
  onTransImmat(v: string | null): void { this.transImmat.set(v ?? ''); this.rechargerTransactions(); }
  onTransChauf(v: string | null): void { this.transChauf.set(v ?? ''); this.rechargerTransactions(); }
  onTransDateDebut(e: Event): void { this.transDateDebut.set((e.target as HTMLInputElement).value); this.rechargerTransactions(); }
  onTransDateFin(e: Event):   void { this.transDateFin.set((e.target as HTMLInputElement).value);   this.rechargerTransactions(); }
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
    // Pages de 1000 (taille maximale acceptée par le serveur) jusqu'à la dernière
    const lignes: any[] = [];
    const page = (n: number) => this.api.getTransactions({ ...this.buildTransFilters(), page: n, page_size: 1000 }).subscribe({
      next: (res) => {
        lignes.push(...(res.results ?? []));
        if (res.next) { page(n + 1); return; }
        this.exporting.set(false);
        const numeriques = new Set(this.allColumns.filter(c => this.isNumericCol(c.key)).map(c => c.key));
        const cell = (v: any, num = false) => {
          let t = v === null || v === undefined ? '' : String(v);
          if (num && t) t = t.replace('.', ',');      // décimales à la virgule pour Excel
          return `"${t.replace(/"/g, '""')}"`;
        };
        const fr = (d: string | null) => d ? d.split('-').reverse().join('/') : '';
        const hdrs = [...this.allColumns.map(c => c.label), 'Annulation', 'Vente annulée', 'Véhicule du parc'].map(h => cell(h)).join(';');
        const data = lignes.map((t: any) => [
          ...this.allColumns.map(c => cell(c.key === 'date_transaction' ? fr(t[c.key]) : t[c.key], numeriques.has(c.key))),
          cell(t.est_annulation ? 'Oui' : ''), cell(t.est_annulee ? 'Oui' : ''), cell(t.vehicule_connu ? 'Oui' : 'Non'),
        ].join(';')).join('\r\n');
        this.downloadCsv('\uFEFF' + hdrs + '\r\n' + data, `transactions_total_${new Date().toISOString().split('T')[0]}.csv`);
      },
      error: () => this.exporting.set(false),
    });
    page(1);
  }

  private downloadCsv(csv: string, filename: string): void {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }
}
