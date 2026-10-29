// UbiFleet — Sinistre Detail Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { SinistreApiService } from '../../../core/services/api.service';
import { Sinistre, StatutSinistre, TypeSinistre } from '../../../core/models';

@Component({
  selector: 'ubi-sinistre-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './sinistre-detail.component.html',
  styleUrls: ['./sinistre-detail.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SinistreDetailComponent implements OnInit {
  id = input.required<string>();

  private router      = inject(Router);
  private fb          = inject(FormBuilder);
  private sinistreApi = inject(SinistreApiService);

  sinistre      = signal<Sinistre | null>(null);
  loading       = signal(true);
  error         = signal('');
  actionLoading = signal(false);
  actionSuccess = signal('');
  actionError   = signal('');
  showStatutModal = signal(false);

  statutForm = this.fb.group({
    statut: ['', Validators.required],
    notes:  [''],
  });

  get sf() { return this.statutForm.controls; }

  readonly statutsDisponibles = [
    { value: 'en_instruction', label: 'Mettre en instruction' },
    { value: 'expertise',      label: 'Expertise en cours' },
    { value: 'reparation',     label: 'En réparation' },
    { value: 'indemnise',      label: 'Indemnisé' },
    { value: 'clos',           label: 'Clôturer le dossier' },
    { value: 'conteste',       label: 'Contesté' },
  ];

  ngOnInit(): void {
    this.sinistreApi.getById(this.id()).subscribe({
      next:  (s) => { this.sinistre.set(s); this.loading.set(false); },
      error: (err) => {
        this.error.set(err?.status === 0 ? 'Serveur inaccessible.' : 'Sinistre introuvable.');
        this.loading.set(false);
      },
    });
  }

  openStatutModal(): void {
    const s = this.sinistre();
    if (s) this.statutForm.patchValue({ statut: s.statut, notes: '' });
    this.showStatutModal.set(true);
  }

  closeStatutModal(): void {
    this.showStatutModal.set(false);
  }

  submitStatut(): void {
    if (this.statutForm.invalid || this.actionLoading()) return;
    this.actionLoading.set(true);
    this.actionError.set('');

    const statut = this.statutForm.value.statut!;
    this.sinistreApi.changerStatut(this.id(), statut).subscribe({
      next: () => {
        this.actionLoading.set(false);
        this.actionSuccess.set('Statut mis à jour avec succès.');
        this.closeStatutModal();
        this.sinistreApi.getById(this.id()).subscribe({
          next: (s) => this.sinistre.set(s), error: () => {},
        });
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.actionError.set(err?.error?.detail ?? 'Erreur lors de la mise à jour.');
      },
    });
  }

  goToEdit(): void { this.router.navigate(['/sinistres', this.id(), 'modifier']); }
  goBack(): void   { this.router.navigate(['/sinistres']); }

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
}
