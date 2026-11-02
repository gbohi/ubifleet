// UbiFleet — Intervention Form Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { catchError, forkJoin, of } from 'rxjs';
import { EntretienApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { OptionVehicule, OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';

@Component({
  selector: 'ubi-intervention-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, SelectRechercheComponent],
  templateUrl: './intervention-form.component.html',
  styleUrls: ['./intervention-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InterventionFormComponent implements OnInit {
  id = input<string | undefined>(undefined);

  private fb           = inject(FormBuilder);
  private router       = inject(Router);
  private entretienApi = inject(EntretienApiService);
  private options      = inject(OptionsSaisieService);

  isEditMode   = computed(() => !!this.id());
  types        = signal<any[]>([]);
  prestataires = signal<OptionRecherche[]>([]);
  /** Véhicules : immatriculation seule, recherche à la saisie (comme les autres formulaires). */
  vehicules    = signal<OptionVehicule[]>([]);
  vehiculeChoisi = computed(() => this.vehicules().find(v => v.value === this.vehiculeId()) ?? null);
  private vehiculeId = signal<string>('');
  agenceNom    = signal('');
  statutActuel = signal('planifie');
  loading      = signal(false);
  saving       = signal(false);
  error        = signal('');
  success      = signal('');

  readonly priorites = [
    { value: 'critique', label: 'Critique' },
    { value: 'haute',    label: 'Haute' },
    { value: 'normale',  label: 'Normale' },
    { value: 'basse',    label: 'Basse' },
  ];

  private readonly statutsFormulaire = [
    { value: 'planifie',      label: 'Planifié' },
    { value: 'en_cours',      label: 'En cours' },
    { value: 'attente_piece', label: 'Attente de pièces' },
  ];
  /** Terminée / annulée : statut affiché, non modifiable (clôture et annulation depuis la fiche). */
  statuts = computed(() => ['termine', 'annule'].includes(this.statutActuel())
    ? [{ value: this.statutActuel(), label: this.statutActuel() === 'termine' ? 'Terminé' : 'Annulé' }]
    : this.statutsFormulaire);

  form = this.fb.group({
    vehicule:              ['', Validators.required],
    type_intervention:     ['', Validators.required],
    prestataire:           [null as string | null],
    date_planifiee:        ['', Validators.required],
    kilometrage_intervention: [null as number | null],
    cout_estime:           [0, [Validators.required, Validators.min(0)]],
    priorite:              ['normale', Validators.required],
    statut:                ['planifie', Validators.required],
    description:           [''],
  });

  get f() { return this.form.controls; }

  ngOnInit(): void {
    this.entretienApi.getTypes().subscribe({
      next: (types) => this.types.set(Array.isArray(types) ? types : []),
      error: () => this.types.set([]),
    });
    this.entretienApi.getPrestataires({ page_size: 500, is_active: true }).subscribe({
      next: (res: any) => this.prestataires.set((Array.isArray(res) ? res : res.results ?? [])
        .map((p: any) => ({ value: p.id, label: p.nom + (p.ville ? ` (${p.ville})` : '') }))),
      error: () => {},
    });
    this.options.vehicules().subscribe({ next: l => this.vehicules.set(l), error: () => {} });

    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.entretienApi.getById(this.id()!).subscribe({
        next: (i: any) => {
          this.form.patchValue({
            vehicule:              i.vehicule,
            type_intervention:     i.type_intervention,
            prestataire:           i.prestataire,
            date_planifiee:        i.date_planifiee,
            kilometrage_intervention: i.kilometrage_intervention,
            cout_estime:           Number(i.cout_estime),
            priorite:              i.priorite,
            statut:                i.statut,
            description:           i.description,
          });
          this.vehiculeId.set(i.vehicule);
          this.agenceNom.set(i.agence_nom ?? '');
          this.statutActuel.set(i.statut);
          // Clôturée : le véhicule ne change plus, le statut se gère depuis la fiche
          if (['termine', 'annule'].includes(i.statut)) {
            this.form.controls.vehicule.disable();
            this.form.controls.statut.disable();
          }
          // Un type désactivé reste proposé pour l'intervention qui l'utilise
          if (i.type_intervention && !this.types().some(t => t.id === i.type_intervention)) {
            this.types.update(l => [...l, { id: i.type_intervention, nom: i.type_nom + ' (désactivé)' }]);
          }
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Impossible de charger les données.');
          this.loading.set(false);
        },
      });
    }
  }

  /** Choix du véhicule : agence et kilométrage proposés d'après sa fiche. */
  choisirVehicule(id: string | null): void {
    this.vehiculeId.set(id ?? '');
    const v = this.vehicules().find(x => x.value === id);
    this.agenceNom.set('');
    if (v && !this.form.value.kilometrage_intervention) this.form.patchValue({ kilometrage_intervention: v.km || null });
  }

  // ── Documents de planification ─────────────────────────────────
  docsPlanif      = signal<File[]>([]);
  docsUploading   = signal(false);

  onDocsPlanifChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files) return;
    this.docsPlanif.set(Array.from(input.files));
  }

  removeDocPlanif(index: number): void {
    const files = [...this.docsPlanif()];
    files.splice(index, 1);
    this.docsPlanif.set(files);
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

    // Création : champs vides omis ; modification : un champ vidé est envoyé (null) pour être effacé
    const raw = this.form.value;
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v;
      else if (this.isEditMode() && ['prestataire', 'kilometrage_intervention', 'description'].includes(k))
        payload[k] = k === 'description' ? '' : null;
    });

    const req = this.isEditMode()
      ? this.entretienApi.update(this.id()!, payload)
      : this.entretienApi.create(payload);

    req.subscribe({
      next: (i) => {
        this.saving.set(false);
        this.success.set(this.isEditMode()
          ? 'Intervention modifiée.' : 'Intervention planifiée.');
        // Documents de planification envoyés avant d'ouvrir la fiche
        const fichiers = this.docsPlanif();
        if (!fichiers.length) { setTimeout(() => this.router.navigate(['/entretien', i.id]), 800); return; }
        forkJoin(fichiers.map(f => this.entretienApi.uploadDocument(i.id, f, 'planification').pipe(
          catchError(err => of({ erreur: `${f.name} : ${messageErreurApi(err, 'envoi impossible')}` })))))
          .subscribe(res => {
            const echecs = res.filter((r: any) => r?.erreur).map((r: any) => r.erreur);
            if (echecs.length) { this.error.set('Intervention enregistrée, mais : ' + echecs.join(' ; ')); return; }
            this.router.navigate(['/entretien', i.id]);
          });
      },
      error: (err) => {
        this.saving.set(false);
        if (err?.error && typeof err.error === 'object') {
          this.error.set(messageErreurApi(err, 'Enregistrement impossible.'));
        } else if (err?.status === 0) {
          this.error.set('Serveur inaccessible.');
        } else {
          this.error.set('Une erreur est survenue.');
        }
      },
    });
  }

  cancel(): void {
    if (this.isEditMode()) {
      this.router.navigate(['/entretien', this.id()]);
    } else {
      this.router.navigate(['/entretien']);
    }
  }
}
