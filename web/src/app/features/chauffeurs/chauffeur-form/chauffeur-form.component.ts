// UbiFleet — Chauffeur Form Component (Angular 18 — Ajout & Modification)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { ChauffeurApiService, AgenceApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';

@Component({
  selector: 'ubi-chauffeur-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './chauffeur-form.component.html',
  styleUrls: ['./chauffeur-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChauffeurFormComponent implements OnInit {
  id = input<string | undefined>(undefined);

  private fb           = inject(FormBuilder);
  private router       = inject(Router);
  private chauffeurApi = inject(ChauffeurApiService);
  private agenceApi    = inject(AgenceApiService);

  isEditMode = computed(() => !!this.id());
  agences    = signal<Agence[]>([]);
  loading    = signal(false);
  saving     = signal(false);
  error      = signal('');
  success    = signal('');

  readonly statutsDisponibles = [
    { value: 'actif',    label: 'Actif' },
    { value: 'conge',    label: 'En congé' },
    { value: 'absent',   label: 'Absent' },
    { value: 'suspendu', label: 'Suspendu' },
  ];
  /** Statuts proposés : « Départ » seulement pour un chauffeur déjà parti (l'archivage se fait depuis la liste). */
  statutsProposes = computed(() => this.statutInitial() === 'depart'
    ? [...this.statutsDisponibles, { value: 'depart', label: 'Départ' }] : this.statutsDisponibles);
  private statutInitial = signal('');

  readonly categoriesPermis = ['B', 'C', 'D', 'B·C', 'B·D', 'C·D', 'B·C·D'];

  form = this.fb.group({
    nom:                  ['', [Validators.required, Validators.maxLength(100)]],
    prenom:               ['', [Validators.required, Validators.maxLength(100)]],
    matricule:            ['', [Validators.required, Validators.maxLength(20)]],
    date_naissance:       [''],
    telephone:            ['', Validators.maxLength(20)],
    email:                ['', Validators.email],
    adresse:              [''],
    numero_chauffeur_total: [''],
    numero_permis:        ['', Validators.required],
    categories_permis:    ['B', Validators.required],
    date_obtention_permis: [''],
    date_expiration_permis:['', Validators.required],
    agence:               ['', Validators.required],
    statut:               ['actif', Validators.required],
    notes:                [''],
  });

  get f() { return this.form.controls; }

  ngOnInit(): void {
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => {},
    });

    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.chauffeurApi.getById(this.id()!).subscribe({
        next: (c) => {
          this.form.patchValue({
            nom:                    c.nom,
            prenom:                 c.prenom,
            matricule:              c.matricule,
            date_naissance:         c.date_naissance ?? '',
            telephone:              c.telephone,
            email:                  c.email,
            adresse:                (c as any).adresse ?? '',
            numero_chauffeur_total: (c as any).numero_chauffeur_total ?? '',
            numero_permis:          c.numero_permis,
            categories_permis:      c.categories_permis,
            date_obtention_permis:  (c as any).date_obtention_permis ?? '',
            date_expiration_permis: c.date_expiration_permis ?? '',
            agence:                 c.agence,
            statut:                 c.statut,
            notes:                  (c as any).notes ?? '',
          });
          this.statutInitial.set(c.statut);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Impossible de charger les données du chauffeur.');
          this.loading.set(false);
        },
      });
    }
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

    // Création : champs vides omis. Modification : un champ vidé est envoyé (null pour les
    // dates) pour être effacé côté serveur.
    const raw = this.form.value;
    const DATES = ['date_naissance', 'date_obtention_permis', 'date_expiration_permis'];
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([key, val]) => {
      const vide = val === '' || val === null || val === undefined;
      if (!vide) payload[key] = typeof val === 'string' ? val.trim() : val;
      else if (this.isEditMode()) payload[key] = DATES.includes(key) ? null : '';
    });

    const req = this.isEditMode()
      ? this.chauffeurApi.update(this.id()!, payload)
      : this.chauffeurApi.create(payload);

    req.subscribe({
      next: (c) => {
        this.saving.set(false);
        this.success.set(this.isEditMode()
          ? 'Chauffeur modifié avec succès.'
          : 'Chauffeur créé avec succès.');
        setTimeout(() => this.router.navigate(['/chauffeurs', c.id]), 1200);
      },
      error: (err) => {
        this.saving.set(false);
        if (err?.error && typeof err.error === 'object') {
          this.error.set(messageErreurApi(err, 'Enregistrement impossible.'));
        } else if (err?.status === 0) {
          this.error.set('Serveur inaccessible. Vérifiez que le backend est démarré.');
        } else {
          this.error.set('Une erreur est survenue. Veuillez réessayer.');
        }
      },
    });
  }

  cancel(): void {
    if (this.isEditMode()) {
      this.router.navigate(['/chauffeurs', this.id()]);
    } else {
      this.router.navigate(['/chauffeurs']);
    }
  }
}
