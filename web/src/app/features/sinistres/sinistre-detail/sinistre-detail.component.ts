// UbiFleet — Sinistre Detail Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { SinistreApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { catchError, forkJoin, of } from 'rxjs';
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
    { value: 'declare',        label: 'Déclaré' },
    { value: 'en_instruction', label: 'Mettre en instruction' },
    { value: 'expertise',      label: 'Expertise en cours' },
    { value: 'reparation',     label: 'En réparation' },
    { value: 'indemnise',      label: 'Indemnisé' },
    { value: 'clos',           label: 'Clôturer le dossier' },
    { value: 'conteste',       label: 'Contesté' },
  ];

  // ── Pièces jointes ──
  readonly acceptDocuments = '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.odt,.ods,.txt';
  readonly typesPiece = [
    { value: 'constat', label: 'Constat amiable' }, { value: 'photo', label: 'Photo' },
    { value: 'facture', label: 'Facture réparation' }, { value: 'rapport', label: "Rapport d'expertise" },
    { value: 'correspondance', label: 'Correspondance assureur' }, { value: 'autre', label: 'Autre' },
  ];
  pjType   = signal('photo');
  pjEnvoi  = signal(false);
  pjErreur = signal('');
  showSuppression = signal(false);

  private recharger(): void {
    this.sinistreApi.getById(this.id()).subscribe({ next: s => this.sinistre.set(s), error: () => {} });
  }
  envoyerPieces(e: Event): void {
    const input = e.target as HTMLInputElement;
    const fichiers = Array.from(input.files ?? []);
    input.value = '';
    if (!fichiers.length) return;
    const trop = fichiers.find(f => f.size > 10 * 1024 * 1024);
    if (trop) { this.pjErreur.set(`${trop.name} dépasse 10 Mo.`); return; }
    this.pjEnvoi.set(true); this.pjErreur.set('');
    forkJoin(fichiers.map(f => this.sinistreApi.envoyerPieceJointe(this.id(), f, this.pjType()).pipe(
      catchError(err => of({ erreur: `${f.name} : ${messageErreurApi(err, 'envoi impossible')}` })))))
      .subscribe(res => {
        this.pjEnvoi.set(false);
        const echecs = res.filter((r: any) => r?.erreur).map((r: any) => r.erreur);
        if (echecs.length) this.pjErreur.set(echecs.join(' ; '));
        this.recharger();
      });
  }
  supprimerPiece(id: string): void {
    if (!confirm('Supprimer cette pièce jointe ?')) return;
    this.sinistreApi.supprimerPieceJointe(id).subscribe({ next: () => this.recharger(), error: () => {} });
  }
  supprimerDossier(): void {
    this.sinistreApi.supprimer(this.id()).subscribe({
      next: () => this.router.navigate(['/sinistres']),
      error: err => this.actionError.set(messageErreurApi(err, 'Suppression impossible.')),
    });
  }
  /** Pièces jointes du dossier (champ « pièces_jointes » de l'API). */
  pieces(s: Sinistre): any[] { return (s as any)['pièces_jointes'] ?? []; }
  tiers(s: Sinistre): string {
    return [s.tiers_nom, s.tiers_immatriculation, s.tiers_assureur].filter(x => !!x).join(' · ') || '—';
  }
  libelleResponsabilite(r?: string): string {
    return ({ total: 'Responsabilité totale', partielle: 'Responsabilité partagée', tiers: 'Tiers responsable',
              force_majeure: 'Force majeure' } as Record<string, string>)[r ?? ''] ?? 'Non déterminée';
  }

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
    this.sinistreApi.changerStatut(this.id(), statut, this.statutForm.value.notes ?? '').subscribe({
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
        this.actionError.set(messageErreurApi(err, 'Erreur lors de la mise à jour.'));
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
