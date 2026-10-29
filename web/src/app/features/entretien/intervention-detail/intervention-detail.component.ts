// UbiFleet — Intervention Detail Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { EntretienApiService } from '../../../core/services/api.service';
import { Intervention, StatutIntervention, PrioriteIntervention } from '../../../core/models';

@Component({
  selector: 'ubi-intervention-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './intervention-detail.component.html',
  styleUrls: ['./intervention-detail.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InterventionDetailComponent implements OnInit {
  id = input.required<string>();

  private router      = inject(Router);
  private fb          = inject(FormBuilder);
  private entretienApi = inject(EntretienApiService);

  intervention  = signal<Intervention | null>(null);
  loading       = signal(true);
  error         = signal('');
  actionLoading = signal(false);
  actionSuccess = signal('');
  actionError   = signal('');

  // Modal démarrage
  showDemarrer  = signal(false);
  dateDemarrage = signal(new Date().toISOString().split('T')[0]);

  // Modal clôture
  showCloture   = signal(false);

  clotureForm = this.fb.group({
    cout_reel:  [null as number | null, Validators.required],
    rapport:    [''],
    prochain_km:[null as number | null],
  });

  get cf() { return this.clotureForm.controls; }

  ngOnInit(): void {
    this.entretienApi.getById(this.id()).subscribe({
      next:  (i) => { this.intervention.set(i); this.loading.set(false); },
      error: (err) => {
        this.error.set(err?.status === 0 ? 'Serveur inaccessible.' : 'Intervention introuvable.');
        this.loading.set(false);
      },
    });
    this.loadDocuments();
  }

  demarrer(): void {
    this.dateDemarrage.set(new Date().toISOString().split('T')[0]);
    this.showDemarrer.set(true);
  }

  closeDemarrer(): void {
    this.showDemarrer.set(false);
  }

  onDateDemarrage(event: Event): void {
    this.dateDemarrage.set((event.target as HTMLInputElement).value);
  }

  submitDemarrer(): void {
    this.actionLoading.set(true);
    this.actionError.set('');
    this.closeDemarrer();
    this.entretienApi.demarrer(this.id(), { date_debut: this.dateDemarrage() }).subscribe({
      next: () => {
        this.actionSuccess.set('Intervention démarrée avec succès.');
        this.actionLoading.set(false);
        this.entretienApi.getById(this.id()).subscribe({
          next: (i) => this.intervention.set(i),
          error: () => {},
        });
      },
      error: (err) => {
        this.actionError.set(err?.error?.detail ?? 'Erreur lors du démarrage.');
        this.actionLoading.set(false);
      },
    });
  }

  openCloture(): void {
    const i = this.intervention();
    if (i?.cout_estime) {
      this.clotureForm.patchValue({ cout_reel: Number(i.cout_estime) });
    }
    this.showCloture.set(true);
  }

  closeCloture(): void {
    this.showCloture.set(false);
    this.clotureForm.reset();
  }

  // ── Documents ──────────────────────────────────────────────────
  documents        = signal<any[]>([]);
  docsCloture      = signal<File[]>([]);

  loadDocuments(): void {
    this.entretienApi.getDocuments(this.id()).subscribe({
      next: (docs) => this.documents.set(docs),
      error: () => {},
    });
  }

  onDocsClotureChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files) return;
    this.docsCloture.set(Array.from(input.files));
  }

  removeDocCloture(index: number): void {
    const files = [...this.docsCloture()];
    files.splice(index, 1);
    this.docsCloture.set(files);
  }

  deleteDocument(docId: string): void {
    this.entretienApi.deleteDocument(docId).subscribe({
      next: () => this.loadDocuments(),
      error: () => {},
    });
  }

  iconDoc(nom: string): string {
    const ext = nom.split('.').pop()?.toLowerCase() ?? '';
    if (['pdf'].includes(ext))              return 'fas fa-file-pdf text-danger';
    if (['doc','docx'].includes(ext))       return 'fas fa-file-word text-primary';
    if (['xls','xlsx'].includes(ext))       return 'fas fa-file-excel text-success';
    if (['jpg','jpeg','png','webp'].includes(ext)) return 'fas fa-file-image';
    return 'fas fa-file';
  }

  submitCloture(): void {
    if (this.clotureForm.invalid || this.actionLoading()) return;
    this.actionLoading.set(true);
    this.actionError.set('');

    const val = this.clotureForm.value;
    const payload: Record<string, any> = {};
    if (val.cout_reel !== null)    payload['cout_reel']   = val.cout_reel;
    if (val.rapport)               payload['rapport']     = val.rapport;
    if (val.prochain_km !== null)  payload['prochain_km'] = val.prochain_km;

    this.entretienApi.terminer(this.id(), payload).subscribe({
      next: () => {
        // Upload documents de clôture
        this.docsCloture().forEach(file => {
          this.entretienApi.uploadDocument(this.id(), file, 'cloture').subscribe({
            next: () => this.loadDocuments(),
            error: () => {},
          });
        });
        this.actionSuccess.set('Intervention clôturée avec succès.');
        this.actionLoading.set(false);
        this.closeCloture();
        this.docsCloture.set([]);
        this.entretienApi.getById(this.id()).subscribe({
          next: (i) => this.intervention.set(i),
          error: () => {},
        });
      },
      error: (err) => {
        this.actionError.set(err?.error?.detail ?? 'Erreur lors de la clôture.');
        this.actionLoading.set(false);
      },
    });
  }

  goToEdit(): void {
    this.router.navigate(['/entretien', this.id(), 'modifier']);
  }

  goBack(): void {
    this.router.navigate(['/entretien']);
  }

  canDemarrer(statut: StatutIntervention): boolean {
    return statut === 'planifie';
  }

  canTerminer(statut: StatutIntervention): boolean {
    return statut === 'en_cours' || statut === 'attente_piece';
  }

  statutBadgeClass(statut: StatutIntervention): string {
    const map: Record<StatutIntervention, string> = {
      planifie: 'badge-navy', en_cours: 'badge-info',
      termine: 'badge-green', annule: 'badge-gray', attente_piece: 'badge-warning',
    };
    return map[statut] ?? 'badge-gray';
  }

  prioriteBadgeClass(priorite: PrioriteIntervention): string {
    const map: Record<PrioriteIntervention, string> = {
      critique: 'badge-danger', haute: 'badge-warning',
      normale: 'badge-info', basse: 'badge-gray',
    };
    return map[priorite] ?? 'badge-gray';
  }
}
