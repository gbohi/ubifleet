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
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';

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

  readonly aujourdhui = new Date().toISOString().split('T')[0];
  clotureErreur = signal('');
  clotureForm = this.fb.group({
    cout_reel:  [null as number | null, [Validators.required, Validators.min(0)]],
    date_fin:   [this.aujourdhui, Validators.required],
    kilometrage_intervention: [null as number | null],
    rapport:    [''],
    prochain_km:[null as number | null],
  });

  // Annulation / suppression
  showAnnulation  = signal(false);
  showSuppression = signal(false);
  motifAnnulation = signal('');

  ouvrirAnnulation(): void { this.actionError.set(''); this.motifAnnulation.set(''); this.showAnnulation.set(true); }
  confirmerAnnulation(): void {
    this.actionLoading.set(true); this.actionError.set('');
    this.entretienApi.annuler(this.id(), this.motifAnnulation().trim()).subscribe({
      next: (i: Intervention) => {
        this.intervention.set(i); this.actionLoading.set(false); this.showAnnulation.set(false);
        this.actionSuccess.set('Intervention annulée.');
      },
      error: err => { this.actionLoading.set(false); this.actionError.set(messageErreurApi(err, 'Annulation impossible.')); },
    });
  }
  confirmerSuppression(): void {
    this.actionError.set('');
    this.entretienApi.supprimer(this.id()).subscribe({
      next: () => this.router.navigate(['/entretien']),
      error: err => this.actionError.set(messageErreurApi(err, 'Suppression impossible.')),
    });
  }

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
        this.actionError.set(messageErreurApi(err, 'Erreur lors du démarrage.'));
        this.actionLoading.set(false);
      },
    });
  }

  openCloture(): void {
    const i: any = this.intervention();
    this.clotureErreur.set('');
    this.clotureForm.reset({
      cout_reel: i?.cout_estime ? Number(i.cout_estime) : null, date_fin: this.aujourdhui,
      kilometrage_intervention: i?.kilometrage_intervention ?? i?.vehicule_km ?? null, rapport: '', prochain_km: null,
    });
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
    if (this.actionLoading()) return;
    if (this.clotureForm.invalid) { this.clotureForm.markAllAsTouched(); return; }
    this.actionLoading.set(true);
    this.actionError.set(''); this.clotureErreur.set('');

    const val = this.clotureForm.value;
    const payload: Record<string, any> = { cout_reel: val.cout_reel, date_fin: val.date_fin };
    if (val.rapport)                         payload['rapport']     = val.rapport;
    if (val.prochain_km !== null)            payload['prochain_km'] = val.prochain_km;
    if (val.kilometrage_intervention !== null) payload['kilometrage_intervention'] = val.kilometrage_intervention;

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
        this.clotureErreur.set(messageErreurApi(err, 'Erreur lors de la clôture.'));
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
    return statut === 'en_cours' || statut === 'attente_piece' || statut === 'planifie';   // clôture directe d'une intervention déjà réalisée
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
