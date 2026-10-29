// UbiFleet — Sinistre Form Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { SinistreApiService, AgenceApiService, VehiculeApiService, ChauffeurApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';

@Component({
  selector: 'ubi-sinistre-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './sinistre-form.component.html',
  styleUrls: ['./sinistre-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SinistreFormComponent implements OnInit {
  id = input<string | undefined>(undefined);

  private fb          = inject(FormBuilder);
  private router      = inject(Router);
  private sinistreApi = inject(SinistreApiService);
  private agenceApi   = inject(AgenceApiService);
  private vehiculeApi = inject(VehiculeApiService);
  private chauffeurApi= inject(ChauffeurApiService);

  isEditMode = computed(() => !!this.id());
  agences    = signal<Agence[]>([]);
  vehicules  = signal<{ id: string; immatriculation: string; designation: string; agenceId: string }[]>([]);
  chauffeurs = signal<{ id: string; nom_complet: string }[]>([]);
  loading    = signal(false);
  saving     = signal(false);
  error      = signal('');
  success    = signal('');

  readonly typesSinistre = [
    { value: 'accident',   label: 'Accident de la route' },
    { value: 'vol',        label: 'Vol de véhicule' },
    { value: 'incendie',   label: 'Incendie' },
    { value: 'vandalisme', label: 'Vandalisme' },
    { value: 'bris_glace', label: 'Bris de glace' },
    { value: 'autre',      label: 'Autre' },
  ];

  form = this.fb.group({
    vehicule:          ['', Validators.required],
    chauffeur:         [null as string | null],
    agence:            ['', Validators.required],
    type_sinistre:     ['accident', Validators.required],
    date_sinistre:     [new Date().toISOString().split('T')[0], Validators.required],
    lieu:              [''],
    description:       ['', Validators.required],
    dommages_estimes:  [0, [Validators.required, Validators.min(0)]],
    cout_reparation:   [null as number | null],
    indemnisation_recue: [null as number | null],
  });

  get f() { return this.form.controls; }

  ngOnInit(): void {
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => {},
    });

    this.vehiculeApi.getAll({ page_size: 200 }).subscribe({
      next: (res) => {
        const list = Array.isArray(res) ? res : (res.results ?? []);
        this.vehicules.set(list.map(v => ({
          id: v.id,
          immatriculation: v.immatriculation,
          designation: v.designation,
          agenceId: v.agence,
        })));
      },
      error: () => {},
    });

    this.chauffeurApi.getAll({ page_size: 200 }).subscribe({
      next: (res) => this.chauffeurs.set(
        res.results.map(c => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });

    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.sinistreApi.getById(this.id()!).subscribe({
        next: (s) => {
          this.form.patchValue({
            vehicule:           s.vehicule,
            chauffeur:          s.chauffeur,
            agence:             s.agence,
            type_sinistre:      s.type_sinistre,
            date_sinistre:      s.date_sinistre,
            lieu:               s.lieu,
            description:        s.description,
            dommages_estimes:   Number(s.dommages_estimes),
            cout_reparation:    s.cout_reparation,
            indemnisation_recue:s.indemnisation_recue,
          });
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Impossible de charger le sinistre.');
          this.loading.set(false);
        },
      });
    }
  }

  onVehiculeChange(event: Event): void {
    const id = (event.target as HTMLSelectElement).value;
    const v  = this.vehicules().find(x => x.id === id);
    if (v?.agenceId) this.form.patchValue({ agence: v.agenceId });
  }

  onSubmit(): void {
    if (this.form.invalid || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    this.success.set('');

    const raw = this.form.value;
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v;
    });

    const req = this.isEditMode()
      ? this.sinistreApi.update(this.id()!, payload)
      : this.sinistreApi.create(payload);

    req.subscribe({
      next: (s) => {
        this.saving.set(false);
        this.success.set(this.isEditMode() ? 'Sinistre modifié.' : 'Sinistre déclaré.');
        setTimeout(() => this.router.navigate(['/sinistres', s.id]), 1200);
      },
      error: (err) => {
        this.saving.set(false);
        if (err?.error && typeof err.error === 'object') {
          const msgs = Object.entries(err.error)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ');
          this.error.set(msgs);
        } else if (err?.status === 0) {
          this.error.set('Serveur inaccessible.');
        } else {
          this.error.set('Une erreur est survenue.');
        }
      },
    });
  }

  cancel(): void { this.router.navigate(['/sinistres']); }
}
