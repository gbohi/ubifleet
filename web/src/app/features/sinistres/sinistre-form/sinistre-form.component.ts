// UbiFleet — Sinistre Form Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { SinistreApiService, ParametrageApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { OptionVehicule, OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';

@Component({
  selector: 'ubi-sinistre-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, SelectRechercheComponent, DecimalPipe],
  templateUrl: './sinistre-form.component.html',
  styleUrls: ['./sinistre-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SinistreFormComponent implements OnInit {
  id = input<string | undefined>(undefined);

  private fb          = inject(FormBuilder);
  private router      = inject(Router);
  private sinistreApi = inject(SinistreApiService);
  private parametrageApi = inject(ParametrageApiService);
  private options     = inject(OptionsSaisieService);

  isEditMode = computed(() => !!this.id());
  /** Véhicules et chauffeurs : immatriculation / nom seuls, recherche à la saisie. */
  vehicules  = signal<OptionVehicule[]>([]);
  chauffeurs = signal<OptionRecherche[]>([]);
  contrats   = signal<{ value: string; label: string; expire: boolean }[]>([]);
  agenceNom  = signal('');
  loading    = signal(false);
  saving     = signal(false);
  error      = signal('');
  success    = signal('');
  readonly aujourdhui = new Date().toISOString().split('T')[0];

  /** Paramètres › Types de sinistre (actifs, plus celui du dossier modifié). */
  typesSinistre = signal<{ value: string; label: string }[]>([]);
  readonly responsabilites = [
    { value: '', label: 'Non déterminée' },
    { value: 'total', label: 'Responsabilité totale' },
    { value: 'partielle', label: 'Responsabilité partagée' },
    { value: 'tiers', label: 'Tiers responsable' },
    { value: 'force_majeure', label: 'Force majeure' },
  ];

  form = this.fb.group({
    vehicule:          ['', Validators.required],
    chauffeur:         [null as string | null],
    contrat_assurance: [null as string | null],
    type_sinistre:     ['', Validators.required],
    responsabilite:    [''],
    date_sinistre:     [this.aujourdhui, Validators.required],
    lieu:              [''],
    kilometrage_sinistre: [null as number | null, Validators.min(0)],
    description:       ['', Validators.required],
    numero_constat:    [''],
    tiers_immatriculation: [''],
    tiers_nom:         [''],
    tiers_assureur:    [''],
    date_declaration_assureur: [''],
    date_expertise:    [''],
    dommages_estimes:  [0, [Validators.required, Validators.min(0)]],
    cout_reparation:   [null as number | null, Validators.min(0)],
    indemnisation_recue: [null as number | null, Validators.min(0)],
    franchise_appliquee: [null as number | null, Validators.min(0)],
    notes:             [''],
  });

  get f() { return this.form.controls; }

  /** Reste à la charge de l'entreprise (coût de réparation − indemnisation), reporté dans les dépenses. */
  resteACharge(): number | null {
    const c = this.form.value.cout_reparation;
    if (c === null || c === undefined || (c as any) === '') return null;
    return Math.max(Number(c) - Number(this.form.value.indemnisation_recue || 0), 0);
  }

  ngOnInit(): void {
    this.parametrageApi.getTypesSinistre().subscribe({
      next: l => this.typesSinistre.set(l.filter(t => t.actif || t.code === this.form.value.type_sinistre)
        .map(t => ({ value: t.code, label: t.libelle }))),
      error: () => {},
    });
    this.options.vehicules().subscribe({ next: l => this.vehicules.set(l), error: () => {} });
    this.options.chauffeurs().subscribe({ next: l => this.chauffeurs.set(l), error: () => {} });

    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.sinistreApi.getById(this.id()!).subscribe({
        next: (s: any) => {
          const champs = Object.keys(this.form.controls);
          this.form.patchValue(Object.fromEntries(champs.map(k => [k, s[k] ?? (this.form.get(k)!.value === null ? null : '')])));
          this.form.patchValue({ dommages_estimes: Number(s.dommages_estimes) });
          this.agenceNom.set(s.agence_nom ?? '');
          this.chargerContrats(s.vehicule);
          this.loading.set(false);
        },
        error: () => { this.error.set('Impossible de charger le sinistre.'); this.loading.set(false); },
      });
    }
  }

  /** Contrats d'assurance du véhicule (le plus récent proposé par défaut à la déclaration). */
  private chargerContrats(vehiculeId: string | null): void {
    this.contrats.set([]);
    if (!vehiculeId) return;
    this.sinistreApi.getContrats({ vehicule: vehiculeId, page_size: 100 }).subscribe({
      next: (r: any) => {
        const l = (Array.isArray(r) ? r : r.results ?? []).sort((a: any, b: any) => b.date_fin.localeCompare(a.date_fin));
        const fr = (d: string) => d.split('-').reverse().join('/');
        this.contrats.set(l.map((c: any) => ({ value: c.id, expire: c.est_expire,
          label: `${c.assureur_nom} — ${c.numero_police} (${c.type_display}, ${fr(c.date_debut)} → ${fr(c.date_fin)})${c.est_expire ? ' — expiré' : ''}` })));
        if (!this.isEditMode() && !this.form.value.contrat_assurance) {
          const valide = l.find((c: any) => !c.est_expire);
          if (valide) this.form.patchValue({ contrat_assurance: valide.id });
        }
      },
      error: () => {},
    });
  }

  choisirVehicule(id: string | null): void {
    const v = this.vehicules().find(x => x.value === id);
    this.agenceNom.set('');
    this.form.patchValue({ contrat_assurance: null });
    if (v && !this.form.value.kilometrage_sinistre) this.form.patchValue({ kilometrage_sinistre: v.km || null });
    this.chargerContrats(id);
  }

  onSubmit(): void {
    if (this.saving()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.error.set('Complétez les champs obligatoires (marqués *).');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.success.set('');

    // Création : champs vides omis ; modification : envoyés vides (null pour listes, dates, montants)
    const TEXTES = ['lieu', 'description', 'numero_constat', 'tiers_immatriculation', 'tiers_nom', 'tiers_assureur',
                    'notes', 'responsabilite', 'type_sinistre'];
    const payload: Record<string, any> = {};
    Object.entries(this.form.value).forEach(([k, v]) => {
      const vide = v === '' || v === null || v === undefined;
      if (!vide) payload[k] = v;
      else if (this.isEditMode()) payload[k] = TEXTES.includes(k) ? '' : null;
    });

    const req = this.isEditMode()
      ? this.sinistreApi.update(this.id()!, payload)
      : this.sinistreApi.create(payload);

    req.subscribe({
      next: (s) => {
        this.saving.set(false);
        this.success.set(this.isEditMode() ? 'Sinistre modifié.' : 'Sinistre déclaré.');
        setTimeout(() => this.router.navigate(['/sinistres', s.id]), 800);
      },
      error: (err) => {
        this.saving.set(false);
        this.error.set(err?.status === 0 ? 'Serveur inaccessible.' : messageErreurApi(err, 'Enregistrement impossible.'));
      },
    });
  }

  cancel(): void { this.router.navigate(['/sinistres']); }
}
