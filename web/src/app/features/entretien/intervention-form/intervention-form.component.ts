// UbiFleet — Intervention Form Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { EntretienApiService, AgenceApiService, VehiculeApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';

@Component({
  selector: 'ubi-intervention-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './intervention-form.component.html',
  styleUrls: ['./intervention-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InterventionFormComponent implements OnInit {
  id = input<string | undefined>(undefined);

  private fb           = inject(FormBuilder);
  private router       = inject(Router);
  private entretienApi = inject(EntretienApiService);
  private agenceApi    = inject(AgenceApiService);
  private vehiculeApi  = inject(VehiculeApiService);

  isEditMode   = computed(() => !!this.id());
  agences      = signal<Agence[]>([]);
  types        = signal<any[]>([]);
  prestataires = signal<any[]>([]);
  vehicules    = signal<{ id: string; immatriculation: string; designation: string; agenceId: string }[]>([]);
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

  readonly statuts = [
    { value: 'planifie',      label: 'Planifié' },
    { value: 'en_cours',      label: 'En cours' },
    { value: 'attente_piece', label: 'Attente de pièces' },
  ];

  form = this.fb.group({
    vehicule:              ['', Validators.required],
    type_intervention:     ['', Validators.required],
    prestataire:           [null as string | null],
    agence:                ['', Validators.required],
    date_planifiee:        ['', Validators.required],
    kilometrage_intervention: [null as number | null],
    cout_estime:           [0, [Validators.required, Validators.min(0)]],
    priorite:              ['normale', Validators.required],
    statut:                ['planifie', Validators.required],
    description:           [''],
  });

  get f() { return this.form.controls; }

  ngOnInit(): void {
    // Charger les données de référence en parallèle
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => {},
    });

    this.entretienApi.getTypes().subscribe({
      next: (types) => this.types.set(Array.isArray(types) ? types : []),
      error: () => this.types.set([]),
    });

    this.entretienApi.getPrestataires().subscribe({
      next: (res) => this.prestataires.set(res.results),
      error: () => {},
    });

    this.vehiculeApi.getAll({ page_size: 100 }).subscribe({
      next: (res) => {
        const list = Array.isArray(res) ? res : (res.results ?? []);
        this.vehicules.set(
          list.map(v => ({
            id: v.id,
            immatriculation: v.immatriculation,
            designation: v.designation,
            agenceId: v.agence,
          }))
        );
      },
      error: () => this.vehicules.set([]),
    });

    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.entretienApi.getById(this.id()!).subscribe({
        next: (i) => {
          this.form.patchValue({
            vehicule:              i.vehicule,
            type_intervention:     i.type_intervention,
            prestataire:           i.prestataire,
            agence:                i.agence,
            date_planifiee:        i.date_planifiee,
            kilometrage_intervention: i.kilometrage_intervention,
            cout_estime:           Number(i.cout_estime),
            priorite:              i.priorite,
            statut:                i.statut,
            description:           i.description,
          });
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Impossible de charger les données.');
          this.loading.set(false);
        },
      });
    }
  }

  onVehiculeChange(event: Event): void {
    const vehiculeId = (event.target as HTMLSelectElement).value;
    const vehicule = this.vehicules().find(v => v.id === vehiculeId);
    if (vehicule && vehicule.agenceId) {
      this.form.patchValue({ agence: vehicule.agenceId });
    }
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

  private uploadDocuments(interventionId: string, files: File[], typeDoc: string): void {
    files.forEach(file => {
      this.entretienApi.uploadDocument(interventionId, file, typeDoc).subscribe({
        next: () => {},
        error: () => {},
      });
    });
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
      ? this.entretienApi.update(this.id()!, payload)
      : this.entretienApi.create(payload);

    req.subscribe({
      next: (i) => {
        this.saving.set(false);
        this.success.set(this.isEditMode()
          ? 'Intervention modifiée.' : 'Intervention planifiée.');
        // Upload des documents de planification
        if (this.docsPlanif().length > 0) {
          this.uploadDocuments(i.id, this.docsPlanif(), 'planification');
        }
        setTimeout(() => this.router.navigate(['/entretien', i.id]), 1200);
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

  cancel(): void {
    if (this.isEditMode()) {
      this.router.navigate(['/entretien', this.id()]);
    } else {
      this.router.navigate(['/entretien']);
    }
  }
}
