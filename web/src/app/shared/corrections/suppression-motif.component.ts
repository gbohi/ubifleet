// UbiFleet — Confirmation de suppression d'un plein ou d'un relevé, avec motif
//
// Le motif est obligatoire pour une saisie sortie de la fenêtre de saisie
// (suppression hors délai), facultatif sinon. Il est conservé dans le journal
// des corrections.
import { Component, ChangeDetectionStrategy, input, output, signal } from '@angular/core';

@Component({
  selector: 'ubi-suppression-motif',
  standalone: true,
  template: `
    <div class="modal-backdrop" (click)="annuler.emit()">
      <div class="modal-container sm-modal" (click)="$event.stopPropagation()" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div class="modal-title"><i class="fas fa-trash" style="color:var(--danger);margin-right:8px"></i>{{ titre() }}</div>
          <button class="btn-close-modal" (click)="annuler.emit()" aria-label="Fermer"><i class="fas fa-times"></i></button>
        </div>
        <p class="sm-texte">{{ message() }}</p>
        @if (motifRequis()) {
          <p class="sm-alerte"><i class="fas fa-history"></i> Saisie hors délai : le motif est obligatoire.</p>
        }
        <div class="form-group">
          <label class="sm-label" for="sm-motif">Motif {{ motifRequis() ? '*' : '(facultatif)' }}</label>
          <textarea id="sm-motif" class="form-control" rows="3" [value]="motif()"
                    (input)="motif.set($any($event.target).value)"
                    placeholder="ex. Doublon, saisi sur le mauvais véhicule…"></textarea>
        </div>
        @if (erreur()) { <div class="sm-erreur"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }
        <div class="sm-actions">
          <button type="button" class="btn btn-outline" (click)="annuler.emit()">Annuler</button>
          <button type="button" class="btn btn-danger" [disabled]="enCours() || (motifRequis() && !motif().trim())"
                  (click)="confirmer.emit(motif().trim())">
            @if (enCours()) { <i class="fas fa-circle-notch fa-spin"></i> } @else { <i class="fas fa-trash"></i> }
            Supprimer
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .sm-modal { width: 460px; }
    .sm-texte { margin: -8px 0 14px; font-size: 13.5px; color: var(--gray-700); }
    .sm-alerte { margin: 0 0 12px; font-size: 12.5px; color: #b45309; background: var(--warning-light);
                 padding: 8px 10px; border-radius: 8px; display: flex; gap: 6px; align-items: baseline; }
    .sm-label { display: block; font-size: 12.5px; font-weight: 600; color: var(--gray-700); margin-bottom: 6px; }
    .sm-erreur { margin-top: 10px; font-size: 12.5px; color: var(--danger); }
    .sm-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SuppressionMotifComponent {
  titre       = input('Supprimer');
  message     = input('');
  motifRequis = input(false);
  enCours     = input(false);
  erreur      = input('');

  confirmer = output<string>();
  annuler   = output<void>();

  motif = signal('');
}
