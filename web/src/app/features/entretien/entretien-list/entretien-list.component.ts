// UbiFleet — Entretien List Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { EntretienStore } from '../../../store/entretien/entretien.store';
import { AgenceApiService, EntretienApiService } from '../../../core/services/api.service';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable, map, of, switchMap } from 'rxjs';
import { exporterCsv } from '../../carburant/analyses/filtres-analyse.component';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { OptionVehicule, OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';
import { Agence, Intervention, StatutIntervention, PrioriteIntervention } from '../../../core/models';

@Component({
  selector: 'ubi-entretien-list',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule, SelectRechercheComponent],
  templateUrl: './entretien-list.component.html',
  styleUrls: ['./entretien-list.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EntretienListComponent implements OnInit {
  store      = inject(EntretienStore);
  private router    = inject(Router);
  private agenceApi = inject(AgenceApiService);

  agences  = signal<Agence[]>([]);
  private entretienApi = inject(EntretienApiService);
  private options = inject(OptionsSaisieService);
  private fb = inject(FormBuilder);
  vehicules = signal<OptionVehicule[]>([]);
  /** Compteurs de toutes les interventions filtrées (pas seulement la page affichée). */
  synthese = signal<any | null>(null);

  // ── Pneus ──
  pneus        = signal<any[]>([]);
  pneusVue     = signal<'a_changer' | 'tous'>('a_changer');
  pneusVehicule = signal('');
  pneuEdite    = signal<any | null | undefined>(undefined);   // undefined = fenêtre fermée
  pneuErreur   = signal('');
  pneuASupprimer = signal<any | null>(null);
  readonly positions = [
    { value: 'av_gauche', label: 'Avant gauche' }, { value: 'av_droit', label: 'Avant droit' },
    { value: 'ar_gauche', label: 'Arrière gauche' }, { value: 'ar_droit', label: 'Arrière droit' },
    { value: 'secours', label: 'Roue de secours' },
  ];
  readonly statutsPneu = [
    { value: 'en_service', label: 'En service' }, { value: 'a_changer', label: 'À changer' }, { value: 'change', label: 'Changé' },
  ];
  pneuForm = this.fb.group({
    vehicule: ['', Validators.required], position: ['av_gauche', Validators.required], marque: [''], dimension: [''],
    date_montage: [new Date().toISOString().split('T')[0], Validators.required],
    kilometrage_montage: [0, [Validators.required, Validators.min(0)]],
    kilometrage_remplacement: [null as number | null], statut: ['en_service', Validators.required],
    cout: [0, Validators.min(0)], notes: [''],
  });

  exportEnCours = signal(false);
  /** Export Excel de toutes les interventions filtrées (toutes les pages). */
  exporter(): void {
    if (this.exportEnCours()) return;
    const f = this.store.filters();
    const params: Record<string, any> = {};
    if (f.search) params['search'] = f.search;
    if (f.agence) params['agence'] = f.agence;
    if (f.vehicule) params['vehicule'] = f.vehicule;
    if (f.priorite) params['priorite'] = f.priorite;
    if (f.statut === 'en_retard') params['en_retard'] = 1; else if (f.statut) params['statut'] = f.statut;
    const page = (n: number): Observable<any[]> => this.entretienApi.getInterventions({ ...params, page: n, page_size: 1000 }).pipe(
      switchMap((r: any) => r.next ? page(n + 1).pipe(map(suite => [...r.results, ...suite])) : of(r.results ?? [])));
    this.exportEnCours.set(true);
    const fr = (d: string | null) => d ? d.split('-').reverse().join('/') : '';
    page(1).subscribe({
      next: lignes => {
        this.exportEnCours.set(false);
        exporterCsv(`interventions_${new Date().toISOString().slice(0, 10)}.csv`,
          ['Véhicule', 'Type', 'Catégorie', 'Prestataire', 'Agence', 'Date planifiée', 'Début', 'Fin', 'Km', 'Priorité',
           'Statut', 'Coût estimé (FCFA)', 'Coût réel (FCFA)', 'Description', 'Rapport'],
          lignes.map((i: any) => [i.vehicule_immat, i.type_nom, i.type_categorie, i.prestataire_nom ?? '', i.agence_nom,
            fr(i.date_planifiee), fr(i.date_debut), fr(i.date_fin), i.kilometrage_intervention ?? '', i.priorite_display,
            i.statut_display, Number(i.cout_estime) || 0, i.cout_reel !== null ? Number(i.cout_reel) : '',
            i.description ?? '', i.rapport_intervention ?? '']));
      },
      error: () => this.exportEnCours.set(false),
    });
  }

  chargerSynthese(): void {
    const f = this.store.filters();
    const p: Record<string, any> = {};
    if (f.search) p['search'] = f.search;
    if (f.agence) p['agence'] = f.agence;
    if (f.vehicule) p['vehicule'] = f.vehicule;
    this.entretienApi.getSynthese(p).subscribe({ next: s => this.synthese.set(s), error: () => {} });
  }
  private recharger(): void { this.store.loadInterventions(); this.chargerSynthese(); }
  onVehiculeFilter(id: string | null): void { this.store.setFilter('vehicule', id ?? ''); this.recharger(); }

  chargerPneus(): void {
    const p: Record<string, any> = { page_size: 500 };
    if (this.pneusVehicule()) p['vehicule'] = this.pneusVehicule();
    const obs: Observable<any> = this.pneusVue() === 'a_changer' && !this.pneusVehicule()
      ? this.entretienApi.getPneusAChanger() : this.entretienApi.getPneus(p);
    obs.subscribe({ next: (r: any) => this.pneus.set(Array.isArray(r) ? r : (r.results ?? [])), error: () => this.pneus.set([]) });
  }
  ouvrirPneu(p: any | null): void {
    this.pneuErreur.set('');
    this.pneuForm.reset(p ? {
      vehicule: p.vehicule, position: p.position, marque: p.marque, dimension: p.dimension, date_montage: p.date_montage,
      kilometrage_montage: p.kilometrage_montage, kilometrage_remplacement: p.kilometrage_remplacement, statut: p.statut,
      cout: Number(p.cout), notes: p.notes,
    } : { vehicule: this.pneusVehicule() || '', position: 'av_gauche', date_montage: new Date().toISOString().split('T')[0],
          kilometrage_montage: this.vehicules().find(v => v.value === this.pneusVehicule())?.km ?? 0, statut: 'en_service', cout: 0 });
    this.pneuEdite.set(p);
  }
  choisirVehiculePneu(id: string | null): void {
    const v = this.vehicules().find(x => x.value === id);
    if (v && !this.pneuEdite()) this.pneuForm.patchValue({ kilometrage_montage: v.km });
  }
  enregistrerPneu(): void {
    if (this.pneuForm.invalid) { this.pneuForm.markAllAsTouched(); this.pneuErreur.set('Complétez les champs obligatoires.'); return; }
    const v: Record<string, any> = { ...this.pneuForm.getRawValue() };
    for (const k of ['marque', 'dimension', 'notes']) v[k] = v[k] ?? '';     // texte vide, pas null
    if (v['kilometrage_remplacement'] !== null && v['kilometrage_remplacement'] <= (v['kilometrage_montage'] ?? 0)) {
      this.pneuErreur.set('Le kilométrage de remplacement doit être supérieur au kilométrage de montage.'); return;
    }
    this.entretienApi.enregistrerPneu(v, this.pneuEdite()?.id).subscribe({
      next: () => { this.pneuEdite.set(undefined); this.chargerPneus(); this.chargerSynthese(); },
      error: err => this.pneuErreur.set(messageErreurApi(err, 'Enregistrement impossible.')),
    });
  }
  supprimerPneu(): void {
    const p = this.pneuASupprimer();
    if (!p) return;
    this.entretienApi.supprimerPneu(p.id).subscribe({
      next: () => { this.pneuASupprimer.set(null); this.chargerPneus(); this.chargerSynthese(); },
      error: () => this.pneuASupprimer.set(null),
    });
  }
  activeTab = signal<'liste' | 'planifiees' | 'pneus'>('liste');

  // Règle 1 : getters pour les calculs — jamais de filter/map dans le template
  get nbUrgentes(): number {
    return this.store.interventions()
      .filter(i => i.priorite === 'critique' && i.statut === 'planifie')
      .length;
  }

  get nbEnCours(): number {
    return this.store.interventions()
      .filter(i => i.statut === 'en_cours')
      .length;
  }

  get nbTerminees(): number {
    return this.store.interventions()
      .filter(i => i.statut === 'termine')
      .length;
  }

  get coutTotalEstime(): number {
    return this.store.interventions()
      .reduce((acc, i) => acc + Number(i.cout_estime), 0);
  }

  get nbPneusAChanger(): number {
    return this.store.pneusAChanger().length;
  }

  // Chips filtre statut
  readonly statutChips: { label: string; value: string }[] = [
    { label: 'Tous',           value: '' },
    { label: 'Planifiés',      value: 'planifie' },
    { label: 'En cours',       value: 'en_cours' },
    { label: 'Terminés',       value: 'termine' },
    { label: 'Attente pièces', value: 'attente_piece' },
    { label: 'En retard',      value: 'en_retard' },
    { label: 'Annulés',        value: 'annule' },
  ];

  readonly prioriteChips: { label: string; value: string }[] = [
    { label: 'Toutes',    value: '' },
    { label: 'Critique',  value: 'critique' },
    { label: 'Haute',     value: 'haute' },
    { label: 'Normale',   value: 'normale' },
  ];

  ngOnInit(): void {
    this.recharger();
    this.store.loadPlanifiees();
    this.chargerPneus();
    this.options.vehicules().subscribe({ next: l => this.vehicules.set(l), error: () => {} });
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => this.agences.set([]),
    });
  }

  onSearch(event: Event): void {
    this.store.setFilter('search', (event.target as HTMLInputElement).value);
    this.recharger();
  }

  onAgenceFilter(event: Event): void {
    this.store.setFilter('agence', (event.target as HTMLSelectElement).value);
    this.recharger();
  }

  onStatutFilter(value: string): void {
    this.store.setFilter('statut', value);
    this.recharger();
  }

  onPrioriteFilter(value: string): void {
    this.store.setFilter('priorite', value);
    this.recharger();
  }

  resetFilters(): void {
    this.store.resetFilters();
    this.recharger();
  }

  goToDetail(id: string): void {
    this.router.navigate(['/entretien', id]);
  }

  goToNew(): void {
    this.router.navigate(['/entretien', 'nouveau']);
  }

  onPageChange(page: number): void {
    this.store.setPage(page);
    this.store.loadInterventions();
  }

  get totalPages(): number {
    const p = this.store.pagination();
    return Math.ceil(p.total / p.pageSize) || 1;
  }

  get pages(): number[] {
    const total   = this.totalPages;
    const current = this.store.pagination().page;
    const range: number[] = [];
    for (let i = Math.max(1, current - 2); i <= Math.min(total, current + 2); i++) {
      range.push(i);
    }
    return range;
  }

  // Helpers badges — aucune logique dans le template
  statutBadgeClass(statut: StatutIntervention): string {
    const map: Record<StatutIntervention, string> = {
      planifie:      'badge-navy',
      en_cours:      'badge-info',
      termine:       'badge-green',
      annule:        'badge-gray',
      attente_piece: 'badge-warning',
    };
    return map[statut] ?? 'badge-gray';
  }

  prioriteBadgeClass(priorite: PrioriteIntervention): string {
    const map: Record<PrioriteIntervention, string> = {
      critique: 'badge-danger',
      haute:    'badge-warning',
      normale:  'badge-info',
      basse:    'badge-gray',
    };
    return map[priorite] ?? 'badge-gray';
  }

  usurePctClass(pct: number | null): string {
    if (pct === null) return '';
    if (pct >= 90) return 'danger';
    if (pct >= 70) return 'warning';
    return 'green';
  }

  trackById(_: number, item: Intervention): string { return item.id; }
}
