// UbiFleet — Budget & Comptabilité (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DecimalPipe, DatePipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { BudgetStore } from '../../../store/budget/budget.store';
import { AgenceApiService, BudgetApiService } from '../../../core/services/api.service';
import { Agence, BudgetAnnuel, Depense } from '../../../core/models';

@Component({
  selector: 'ubi-budget-list',
  standalone: true,
  imports: [RouterLink, DecimalPipe, DatePipe, ReactiveFormsModule],
  templateUrl: './budget-list.component.html',
  styleUrls: ['./budget-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BudgetListComponent implements OnInit {
  store      = inject(BudgetStore);
  private fb          = inject(FormBuilder);
  private agenceApi   = inject(AgenceApiService);
  private budgetApi   = inject(BudgetApiService);

  agences    = signal<Agence[]>([]);
  budgets    = signal<BudgetAnnuel[]>([]);
  activeTab  = signal<'tableau' | 'depenses' | 'budgets'>('tableau');

  // ── Filtres dépenses ─────────────────────────────────────────────
  filtreDepDateMin  = signal('');
  filtreDepDateMax  = signal('');
  filtreDepCateg    = signal('');
  filtreDepAgence   = signal('');
  filtreDepVehicule = signal('');

  // ── Filtres budgets ──────────────────────────────────────────────
  filtreBudAnnee  = signal(new Date().getFullYear().toString());
  filtreBudAgence = signal('');

  // ── Formulaire budget annuel ─────────────────────────────────────
  showBudgetModal = signal(false);
  editBudgetId    = signal<string | null>(null);
  budgetSaving    = signal(false);
  budgetError     = signal('');

  budgetForm = this.fb.group({
    agence:               ['', Validators.required],
    annee:                [new Date().getFullYear(), Validators.required],
    budget_carburant:     [0, Validators.min(0)],
    budget_entretien:     [0, Validators.min(0)],
    budget_reparations:   [0, Validators.min(0)],
    budget_assurances:    [0, Validators.min(0)],
    budget_pneumatiques:  [0, Validators.min(0)],
    budget_divers:        [0, Validators.min(0)],
    notes:                [''],
  });
  get bf() { return this.budgetForm.controls; }

  // ── Formulaire dépense ───────────────────────────────────────────
  showDepenseModal  = signal(false);
  editDepenseId     = signal<string | null>(null);
  depenseSaving     = signal(false);
  depenseError      = signal('');
  deleteDepenseId   = signal<string | null>(null);
  factureDepense    = signal<Depense | null>(null);

  depenseForm = this.fb.group({
    vehicule:        [''],
    agence:          ['', Validators.required],
    categorie:       ['carburant', Validators.required],
    date_depense:    [new Date().toISOString().split('T')[0], Validators.required],
    montant:         [0, [Validators.required, Validators.min(0.01)]],
    description:     ['', Validators.required],
    fournisseur:     [''],
    numero_facture:  [''],
  });
  get df() { return this.depenseForm.controls; }

  get totalDepenses(): number {
    return this.store.depenses().reduce((a, d) => a + Number(d.montant), 0);
  }
  get budgetTotalAlloue(): number {
    return this.budgets().reduce((a, b) => a + Number(b.budget_total), 0);
  }

  get annees(): number[] {
    const a = new Date().getFullYear();
    return [a, a-1, a-2, a-3];
  }

  readonly categories = [
    { value: 'carburant',  label: 'Carburant' },
    { value: 'entretien',  label: 'Entretien préventif' },
    { value: 'reparation', label: 'Réparation' },
    { value: 'pneus',      label: 'Pneumatiques' },
    { value: 'assurance',  label: 'Assurance' },
    { value: 'sinistre',   label: 'Sinistre' },
    { value: 'controle',   label: 'Contrôle technique' },
    { value: 'peage',      label: 'Péage' },
    { value: 'parking',    label: 'Parking' },
    { value: 'divers',     label: 'Divers' },
  ];

  ngOnInit(): void {
    this.store.loadTableauDeBord();
    this.store.loadDepenses();
    this.agenceApi.getAll().subscribe({
      next: (list: any) => this.agences.set(Array.isArray(list) ? list : (list.results ?? [])),
      error: () => {},
    });
    this.loadBudgets();
  }

  loadBudgets(): void {
    const params: Record<string, any> = {};
    if (this.filtreBudAnnee())  params['annee']  = this.filtreBudAnnee();
    if (this.filtreBudAgence()) params['agence'] = this.filtreBudAgence();
    this.budgetApi.getBudgets(params).subscribe({
      next: (res: any) => this.budgets.set(Array.isArray(res) ? res : (res.results ?? [])),
      error: () => {},
    });
  }

  // ── Filtres dépenses ─────────────────────────────────────────────
  onDepFilter(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement | HTMLSelectElement).value;
    if (field === 'date_min')  this.filtreDepDateMin.set(val);
    if (field === 'date_max')  this.filtreDepDateMax.set(val);
    if (field === 'categorie') this.filtreDepCateg.set(val);
    if (field === 'agence')    this.filtreDepAgence.set(val);
    if (field === 'vehicule')  this.filtreDepVehicule.set(val);
  }

  appliquerFiltresDepenses(): void {
    if (this.filtreDepDateMin())  this.store.setFilter('date_min'  as any, this.filtreDepDateMin());
    if (this.filtreDepDateMax())  this.store.setFilter('date_max'  as any, this.filtreDepDateMax());
    if (this.filtreDepCateg())    this.store.setFilter('categorie' as any, this.filtreDepCateg());
    if (this.filtreDepAgence())   this.store.setFilter('agence'    as any, this.filtreDepAgence());
    if (this.filtreDepVehicule()) this.store.setFilter('vehicule'  as any, this.filtreDepVehicule());
    this.store.loadDepenses();
  }

  // ── Filtres budgets ──────────────────────────────────────────────
  onBudFilter(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement | HTMLSelectElement).value;
    if (field === 'annee')  this.filtreBudAnnee.set(val);
    if (field === 'agence') this.filtreBudAgence.set(val);
    this.loadBudgets();
  }

  onAnneeFilter(event: Event): void {
    this.store.setFilter('annee', (event.target as HTMLSelectElement).value);
    this.store.loadTableauDeBord();
    this.store.loadDepenses();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.store.loadTableauDeBord();
    this.store.loadDepenses();
  }

  onCategorieFilter(event: Event): void {
    this.store.setFilter('categorie', (event.target as HTMLSelectElement).value);
    this.store.loadDepenses();
  }

  // ── Export dépenses ──────────────────────────────────────────────
  exportDepensesExcel(): void {
    const rows = this.store.depenses();
    if (!rows.length) return;
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Date','Véhicule','Agence','Catégorie','Description',
                  'Fournisseur','N° Facture','Montant (FCFA)'].join(sep);
    const data = rows.map((d: Depense) => [
      d.date_depense,
      d.vehicule_immat ?? '—',
      d.agence_nom ?? '—',
      d.categorie_display ?? d.categorie,
      d.description,
      d.fournisseur ?? '',
      d.numero_facture ?? '',
      d.montant,
    ].join(sep)).join(eol);
    this.downloadFile('\uFEFF' + hdrs + eol + data, 'depenses.csv', 'text/csv;charset=utf-8;');
  }

  exportDepensesPdf(): void {
    const rows = this.store.depenses();
    if (!rows.length) return;
    const lines = rows.map((d: Depense) =>
      `<tr>
        <td>${d.date_depense}</td>
        <td>${d.vehicule_immat ?? '—'}</td>
        <td>${d.agence_nom ?? '—'}</td>
        <td>${d.categorie_display ?? d.categorie}</td>
        <td>${d.description}</td>
        <td>${d.fournisseur ?? ''}</td>
        <td style="text-align:right">${Number(d.montant).toLocaleString('fr-FR')} FCFA</td>
      </tr>`
    ).join('');
    const total = this.totalDepenses;
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Dépenses UbiFleet</title>
<style>
  body { font-family: Arial, sans-serif; font-size: 12px; margin: 20px; }
  h2 { color: #092440; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th { background: #092440; color: white; padding: 8px; text-align: left; }
  td { border-bottom: 1px solid #eee; padding: 6px 8px; }
  tr:nth-child(even) td { background: #f9f9f9; }
  .total { font-weight: bold; text-align: right; margin-top: 12px; font-size: 14px; }
  .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
  .logo { font-size: 22px; font-weight: 900; color: #092440; }
  .logo span { color: #5bd988; }
</style></head><body>
<div class="header">
  <div><div class="logo">Ubi<span>Fleet</span></div><div style="color:#666">Rapport des dépenses</div></div>
  <div style="text-align:right;color:#666">Généré le ${new Date().toLocaleDateString('fr-FR')}</div>
</div>
<table><thead><tr>
  <th>Date</th><th>Véhicule</th><th>Agence</th><th>Catégorie</th>
  <th>Description</th><th>Fournisseur</th><th>Montant</th>
</tr></thead><tbody>${lines}</tbody></table>
<div class="total">Total : ${total.toLocaleString('fr-FR')} FCFA</div>
</body></html>`;
    this.printHtml(html);
  }

  // ── Facture PDF d'une dépense ─────────────────────────────────────
  ouvrirFacture(d: Depense): void { this.factureDepense.set(d); }
  fermerFacture(): void { this.factureDepense.set(null); }

  imprimerFacture(d: Depense): void {
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Facture ${d.numero_facture || d.id}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Arial, sans-serif; font-size: 13px; margin: 0; padding: 30px; color: #333; }
  .header { display: flex; justify-content: space-between; margin-bottom: 32px; }
  .logo { font-size: 28px; font-weight: 900; color: #092440; }
  .logo span { color: #5bd988; }
  .facture-title { font-size: 20px; font-weight: 700; color: #092440; margin-bottom: 4px; }
  .meta { color: #666; font-size: 12px; }
  .section { background: #f5f7fa; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
  .section-title { font-size: 11px; font-weight: 700; text-transform: uppercase;
    color: #666; letter-spacing: 0.5px; margin-bottom: 10px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .field { margin-bottom: 8px; }
  .field label { font-size: 11px; color: #999; display: block; }
  .field span { font-weight: 600; font-size: 13px; }
  .montant-box { background: #092440; color: white; border-radius: 10px;
    padding: 20px; text-align: center; }
  .montant-label { font-size: 12px; opacity: 0.7; margin-bottom: 4px; }
  .montant-val { font-size: 28px; font-weight: 900; }
  .badge { display: inline-block; background: #5bd98820; color: #092440;
    border: 1px solid #5bd988; border-radius: 20px; padding: 3px 12px;
    font-size: 11px; font-weight: 700; }
  .footer { border-top: 1px solid #eee; margin-top: 32px; padding-top: 12px;
    font-size: 11px; color: #999; text-align: center; }
  @media print { body { padding: 15px; } }
</style></head><body>
<div class="header">
  <div>
    <div class="logo">Ubi<span>Fleet</span></div>
    <div style="color:#666;font-size:12px;margin-top:4px">Gestion de flotte automobile</div>
  </div>
  <div style="text-align:right">
    <div class="facture-title">REÇU DE DÉPENSE</div>
    <div class="meta">N° ${d.numero_facture || ('DEP-' + d.id.substring(0,8).toUpperCase())}</div>
    <div class="meta">Date : ${new Date(d.date_depense).toLocaleDateString('fr-FR')}</div>
    <div class="meta" style="margin-top:6px"><span class="badge">${d.categorie_display ?? d.categorie}</span></div>
  </div>
</div>

<div class="section">
  <div class="section-title">Informations générales</div>
  <div class="grid-2">
    <div>
      <div class="field"><label>Véhicule</label><span>${d.vehicule_immat ?? '—'}</span></div>
      <div class="field"><label>Agence</label><span>${d.agence_nom ?? '—'}</span></div>
      <div class="field"><label>Fournisseur</label><span>${d.fournisseur || '—'}</span></div>
    </div>
    <div>
      <div class="field"><label>Date de la dépense</label><span>${new Date(d.date_depense).toLocaleDateString('fr-FR')}</span></div>
      <div class="field"><label>N° de facture fournisseur</label><span>${d.numero_facture || '—'}</span></div>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">Description</div>
  <p style="margin:0;font-size:14px">${d.description}</p>
</div>

<div class="montant-box" style="max-width:320px;margin:0 auto">
  <div class="montant-label">MONTANT TOTAL</div>
  <div class="montant-val">${Number(d.montant).toLocaleString('fr-FR')} FCFA</div>
</div>

<div class="footer">
  Document généré par UbiFleet — ${new Date().toLocaleString('fr-FR')}
</div>
</body></html>`;
    this.printHtml(html);
  }

  // ── Export budgets ────────────────────────────────────────────────
  exportBudgetsExcel(): void {
    const rows = this.budgets();
    if (!rows.length) return;
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Agence','Année','Carburant','Entretien','Réparations',
                  'Assurances','Pneumatiques','Divers','Total','Notes'].join(sep);
    const data = rows.map((b: BudgetAnnuel) => [
      b.agence_nom ?? b.agence,
      b.annee,
      b.budget_carburant, b.budget_entretien, b.budget_reparations,
      b.budget_assurances, b.budget_pneumatiques, b.budget_divers,
      b.budget_total,
      b.notes ?? '',
    ].join(sep)).join(eol);
    this.downloadFile('\uFEFF' + hdrs + eol + data, 'budgets_annuels.csv', 'text/csv;charset=utf-8;');
  }

  exportBudgetsPdf(): void {
    const rows = this.budgets();
    if (!rows.length) return;
    const lines = rows.map((b: BudgetAnnuel) => `
      <tr>
        <td>${b.agence_nom ?? b.agence}</td>
        <td style="text-align:center">${b.annee}</td>
        <td style="text-align:right">${Number(b.budget_carburant).toLocaleString('fr-FR')}</td>
        <td style="text-align:right">${Number(b.budget_entretien).toLocaleString('fr-FR')}</td>
        <td style="text-align:right">${Number(b.budget_reparations).toLocaleString('fr-FR')}</td>
        <td style="text-align:right">${Number(b.budget_assurances).toLocaleString('fr-FR')}</td>
        <td style="text-align:right">${Number(b.budget_pneumatiques).toLocaleString('fr-FR')}</td>
        <td style="text-align:right">${Number(b.budget_divers).toLocaleString('fr-FR')}</td>
        <td style="text-align:right;font-weight:700">${Number(b.budget_total).toLocaleString('fr-FR')}</td>
      </tr>`).join('');
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Budgets Annuels UbiFleet</title>
<style>
  body { font-family: Arial, sans-serif; font-size: 11px; margin: 20px; }
  h2 { color: #092440; }
  .logo { font-size: 22px; font-weight: 900; color: #092440; }
  .logo span { color: #5bd988; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th { background: #092440; color: white; padding: 7px 8px; text-align: left; font-size: 10px; }
  td { border-bottom: 1px solid #eee; padding: 5px 8px; }
  tr:nth-child(even) td { background: #f9f9f9; }
</style></head><body>
<div style="display:flex;justify-content:space-between;margin-bottom:20px">
  <div><div class="logo">Ubi<span>Fleet</span></div><div style="color:#666">Budgets annuels</div></div>
  <div style="color:#666;font-size:11px">Généré le ${new Date().toLocaleDateString('fr-FR')}</div>
</div>
<table><thead><tr>
  <th>Agence</th><th>Année</th><th>Carburant</th><th>Entretien</th>
  <th>Réparations</th><th>Assurances</th><th>Pneus</th><th>Divers</th><th>Total</th>
</tr></thead><tbody>${lines}</tbody></table>
</body></html>`;
    this.printHtml(html);
  }

  // ── Export véhicules ─────────────────────────────────────────────
  // (géré dans vehicules-list component)

  // ── Budget modal ─────────────────────────────────────────────────
  openBudgetModal(budget?: BudgetAnnuel): void {
    this.budgetError.set('');
    if (budget) {
      this.editBudgetId.set(budget.id);
      this.budgetForm.patchValue({
        agence:              budget.agence,
        annee:               budget.annee,
        budget_carburant:    Number(budget.budget_carburant),
        budget_entretien:    Number(budget.budget_entretien),
        budget_reparations:  Number(budget.budget_reparations),
        budget_assurances:   Number(budget.budget_assurances),
        budget_pneumatiques: Number(budget.budget_pneumatiques),
        budget_divers:       Number(budget.budget_divers),
        notes:               budget.notes ?? '',
      });
    } else {
      this.editBudgetId.set(null);
      this.budgetForm.reset({
        annee: new Date().getFullYear(),
        budget_carburant: 0, budget_entretien: 0, budget_reparations: 0,
        budget_assurances: 0, budget_pneumatiques: 0, budget_divers: 0,
      });
    }
    this.showBudgetModal.set(true);
  }
  closeBudgetModal(): void { this.showBudgetModal.set(false); }

  saveBudget(): void {
    if (this.budgetForm.invalid || this.budgetSaving()) return;
    this.budgetSaving.set(true);
    const raw = this.budgetForm.value;
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') payload[k] = v;
    });
    const req = this.editBudgetId()
      ? this.budgetApi.updateBudget(this.editBudgetId()!, payload)
      : this.budgetApi.createBudget(payload);
    req.subscribe({
      next: () => { this.budgetSaving.set(false); this.closeBudgetModal(); this.loadBudgets(); },
      error: (err) => {
        this.budgetSaving.set(false);
        this.budgetError.set(err?.error?.detail ?? 'Erreur lors de l\'enregistrement.');
      },
    });
  }

  // ── Dépense modal ─────────────────────────────────────────────────
  openDepenseModal(depense?: Depense): void {
    this.depenseError.set('');
    if (depense) {
      this.editDepenseId.set(depense.id);
      this.depenseForm.patchValue({
        vehicule:       depense.vehicule,
        agence:         depense.agence,
        categorie:      depense.categorie,
        date_depense:   depense.date_depense,
        montant:        Number(depense.montant),
        description:    depense.description,
        fournisseur:    depense.fournisseur,
        numero_facture: depense.numero_facture,
      });
    } else {
      this.editDepenseId.set(null);
      this.depenseForm.reset({
        categorie: 'carburant',
        date_depense: new Date().toISOString().split('T')[0],
        montant: 0,
      });
    }
    this.showDepenseModal.set(true);
  }
  closeDepenseModal(): void { this.showDepenseModal.set(false); }

  saveDepense(): void {
    if (this.depenseForm.invalid || this.depenseSaving()) return;
    this.depenseSaving.set(true);
    const raw = this.depenseForm.value;
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') payload[k] = v;
    });
    const req = this.editDepenseId()
      ? this.budgetApi.updateDepense(this.editDepenseId()!, payload)
      : this.budgetApi.createDepense(payload);
    req.subscribe({
      next: () => {
        this.depenseSaving.set(false);
        this.closeDepenseModal();
        this.store.loadDepenses();
        this.store.loadTableauDeBord();
      },
      error: (err) => {
        this.depenseSaving.set(false);
        this.depenseError.set(err?.error?.detail ?? 'Erreur.');
      },
    });
  }

  confirmDeleteDepense(id: string): void { this.deleteDepenseId.set(id); }
  cancelDeleteDepense(): void            { this.deleteDepenseId.set(null); }
  doDeleteDepense(id: string): void {
    this.budgetApi.deleteDepense(id).subscribe({
      next: () => {
        this.deleteDepenseId.set(null);
        this.store.loadDepenses();
        this.store.loadTableauDeBord();
      },
      error: () => this.deleteDepenseId.set(null),
    });
  }

  // ── Pagination ────────────────────────────────────────────────────
  onPageChange(page: number): void { this.store.setPage(page); this.store.loadDepenses(); }
  get totalPages(): number {
    const p = this.store.pagination();
    return Math.ceil(p.total / p.pageSize) || 1;
  }
  get pages(): number[] {
    const total = this.totalPages; const cur = this.store.pagination().page;
    const range: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(total, cur + 2); i++) range.push(i);
    return range;
  }

  // ── Helpers ───────────────────────────────────────────────────────
  budgetBarWidth(realise: number, total: number): number {
    if (!total) return 0;
    return Math.min((realise / total) * 100, 100);
  }
  budgetBarClass(realise: number, total: number): string {
    if (!total) return 'green';
    const pct = (realise / total) * 100;
    if (pct >= 100) return 'danger';
    if (pct >= 80)  return 'warning';
    return 'green';
  }
  formatFCFA(v: number): string {
    if (!v) return '0';
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000)     return `${(v / 1_000).toFixed(0)}K`;
    return `${v}`;
  }

  private downloadFile(content: string, filename: string, mime: string): void {
    const blob = new Blob([content], { type: mime });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click(); URL.revokeObjectURL(a.href);
  }

  private printHtml(html: string): void {
    const w = window.open('', '_blank', 'width=900,height=700');
    if (!w) return;
    w.document.write(html);
    w.document.close();
    w.focus();
    setTimeout(() => { w.print(); }, 300);
  }
}
