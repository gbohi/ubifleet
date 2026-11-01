// UbiFleet — Sinistres List Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { SinistresStore } from '../../../store/sinistres/sinistres.store';
import { AgenceApiService, ParametrageApiService, SinistreApiService, VehiculeApiService } from '../../../core/services/api.service';
import { Agence, Sinistre, ContratAssurance, StatutSinistre, TypeSinistre } from '../../../core/models';

@Component({
  selector: 'ubi-sinistres-list',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './sinistres-list.component.html',
  styleUrls: ['./sinistres-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SinistresListComponent implements OnInit {
  store       = inject(SinistresStore);
  private router       = inject(Router);
  private fb           = inject(FormBuilder);
  private agenceApi    = inject(AgenceApiService);
  private sinistreApi  = inject(SinistreApiService);
  private vehiculeApi  = inject(VehiculeApiService);
  private parametrageApi = inject(ParametrageApiService);

  agences      = signal<Agence[]>([]);
  vehicules    = signal<{ id: string; immatriculation: string; designation: string }[]>([]);
  assureurs    = signal<any[]>([]);
  allContrats  = signal<ContratAssurance[]>([]);
  contratsLoad = signal(false);
  activeTab    = signal<'sinistres' | 'contrats'>('sinistres');

  // Contrat form
  showContratModal  = signal(false);
  editContratId     = signal<string | null>(null);
  contratSaving     = signal(false);
  contratError      = signal('');
  contratSuccess    = signal('');
  deleteContratId   = signal<string | null>(null);

  contratForm = this.fb.group({
    vehicule:       ['', Validators.required],
    assureur:       ['', Validators.required],
    numero_police:  ['', Validators.required],
    type_contrat:   ['', Validators.required],
    date_debut:     ['', Validators.required],
    date_fin:       ['', Validators.required],
    prime_annuelle: [0, [Validators.required, Validators.min(0)]],
    franchise:      [0, [Validators.min(0)]],
  });

  get cf() { return this.contratForm.controls; }

  /** Paramètres › Types de contrat d'assurance (actifs, plus celui du contrat modifié). */
  private typesContratTous = signal<{ value: string; label: string; actif: boolean }[]>([]);
  private typeContratEdite = signal('');
  typesContrat = computed(() => this.typesContratTous().filter(t => t.actif || t.value === this.typeContratEdite()));

  readonly statutChips = [
    { label: 'Tous',             value: '' },
    { label: 'Déclaré',          value: 'declare' },
    { label: 'En instruction',   value: 'en_instruction' },
    { label: 'Expertise',        value: 'expertise' },
    { label: 'Réparation',       value: 'reparation' },
    { label: 'Indemnisé',        value: 'indemnise' },
    { label: 'Clos',             value: 'clos' },
  ];

  /** Filtre par type : Paramètres › Types de sinistre. */
  typesChips = signal<{ label: string; value: string }[]>([{ label: 'Tous', value: '' }]);

  // Getters — pas de filter dans le template
  get nbEnCours(): number {
    return this.store.sinistres().filter(s =>
      ['declare','en_instruction','expertise','reparation'].includes(s.statut)
    ).length;
  }

  get totalDommages(): number {
    return this.store.sinistres().reduce((a, s) => a + Number(s.dommages_estimes), 0);
  }

  get nbContratsUrgents(): number {
    return this.store.contratsExpirant().filter(c => c.jours_restants <= 30).length;
  }

  ngOnInit(): void {
    this.parametrageApi.getTypesSinistre().subscribe({
      next: l => this.typesChips.set([{ label: 'Tous', value: '' },
        ...l.filter(t => t.actif).map(t => ({ label: t.libelle, value: t.code }))]),
      error: () => {},
    });
    this.parametrageApi.getTypesContrat().subscribe({
      next: l => this.typesContratTous.set(l.map(t => ({ value: t.code, label: t.libelle, actif: t.actif }))),
      error: () => {},
    });
    this.store.loadSinistres();
    this.store.loadContratsExpirant();
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });
    this.vehiculeApi.getAll({ page_size: 200 }).subscribe({
      next: (res) => {
        const list = Array.isArray(res) ? res : (res.results ?? []);
        this.vehicules.set(list.map(v => ({
          id: v.id, immatriculation: v.immatriculation, designation: v.designation,
        })));
      },
      error: () => {},
    });
    this.sinistreApi.getAssureurs().subscribe({
      next: (list) => this.assureurs.set(Array.isArray(list) ? list : []),
      error: () => {},
    });
  }

  onSearch(event: Event): void {
    this.store.setFilter('search', (event.target as HTMLInputElement).value);
    this.store.loadSinistres();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.store.loadSinistres();
  }

  onStatutFilter(val: string): void {
    this.store.setFilter('statut', val);
    this.store.loadSinistres();
  }

  onTypeFilter(val: string): void {
    this.store.setFilter('type_sinistre', val);
    this.store.loadSinistres();
  }

  goToDetail(id: string): void   { this.router.navigate(['/sinistres', id]); }
  goToNew(): void                 { this.router.navigate(['/sinistres', 'nouveau']); }
  goToEdit(event: Event, id: string): void {
    event.stopPropagation();
    this.router.navigate(['/sinistres', id, 'modifier']);
  }

  onPageChange(page: number): void {
    this.store.setPage(page);
    this.store.loadSinistres();
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

  loadContrats(): void {
    this.contratsLoad.set(true);
    this.sinistreApi.getContrats({ page_size: 100 }).subscribe({
      next: (res) => {
        this.allContrats.set(res.results ?? []);
        this.contratsLoad.set(false);
      },
      error: () => this.contratsLoad.set(false),
    });
  }

  onTabChange(tab: 'sinistres' | 'contrats'): void {
    this.activeTab.set(tab);
    if (tab === 'contrats' && this.allContrats().length === 0) {
      this.loadContrats();
    }
  }

  openContratModal(contrat?: ContratAssurance): void {
    this.contratError.set('');
    this.contratSuccess.set('');
    if (contrat) {
      this.editContratId.set(contrat.id);
      this.typeContratEdite.set(contrat.type_contrat);
      this.contratForm.patchValue({
        vehicule:       contrat.vehicule,
        assureur:       contrat.assureur,
        numero_police:  contrat.numero_police,
        type_contrat:   contrat.type_contrat,
        date_debut:     contrat.date_debut,
        date_fin:       contrat.date_fin,
        prime_annuelle: Number(contrat.prime_annuelle),
        franchise:      Number(contrat.franchise),
      });
    } else {
      this.editContratId.set(null);
      this.typeContratEdite.set('');
      this.contratForm.reset({ type_contrat: '', prime_annuelle: 0, franchise: 0 });
    }
    this.showContratModal.set(true);
  }

  closeContratModal(): void {
    this.showContratModal.set(false);
    this.editContratId.set(null);
  }

  saveContrat(): void {
    if (this.contratForm.invalid || this.contratSaving()) return;
    this.contratSaving.set(true);
    this.contratError.set('');

    const raw = this.contratForm.value;
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v;
    });

    const req = this.editContratId()
      ? this.sinistreApi.updateContrat(this.editContratId()!, payload)
      : this.sinistreApi.createContrat(payload);

    req.subscribe({
      next: () => {
        this.contratSaving.set(false);
        this.contratSuccess.set(this.editContratId() ? 'Contrat modifié.' : 'Contrat créé.');
        this.closeContratModal();
        this.loadContrats();
        this.store.loadContratsExpirant();
      },
      error: (err) => {
        this.contratSaving.set(false);
        if (err?.error && typeof err.error === 'object') {
          const msgs = Object.entries(err.error)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ');
          this.contratError.set(msgs);
        } else {
          this.contratError.set('Une erreur est survenue.');
        }
      },
    });
  }

  confirmDeleteContrat(id: string): void { this.deleteContratId.set(id); }
  cancelDeleteContrat(): void            { this.deleteContratId.set(null); }

  doDeleteContrat(id: string): void {
    this.sinistreApi.deleteContrat(id).subscribe({
      next: () => {
        this.deleteContratId.set(null);
        this.loadContrats();
        this.store.loadContratsExpirant();
      },
      error: () => this.deleteContratId.set(null),
    });
  }

  joursClass(jours: number): string {
    if (jours <= 0)  return 'badge-danger';
    if (jours <= 30) return 'badge-danger';
    if (jours <= 60) return 'badge-warning';
    return 'badge-green';
  }

  statutBadgeClass(statut: StatutSinistre): string {
    const map: Record<string, string> = {
      declare: 'badge-warning', en_instruction: 'badge-info',
      expertise: 'badge-navy', reparation: 'badge-warning',
      indemnise: 'badge-green', clos: 'badge-gray', conteste: 'badge-danger',
    };
    return map[statut] ?? 'badge-gray';
  }

  typeBadgeClass(type: TypeSinistre): string {
    const map: Record<string, string> = {
      accident: 'badge-danger', vol: 'badge-danger',
      incendie: 'badge-danger', vandalisme: 'badge-warning',
      bris_glace: 'badge-info', autre: 'badge-gray',
    };
    return map[type] ?? 'badge-gray';
  }

  contratsJoursClass(jours: number): string {
    if (jours <= 0)  return 'badge-danger';
    if (jours <= 30) return 'badge-danger';
    if (jours <= 60) return 'badge-warning';
    return 'badge-green';
  }

  trackById(_: number, s: Sinistre): string { return s.id; }
  trackContratById(_: number, c: ContratAssurance): string { return c.id; }
}
