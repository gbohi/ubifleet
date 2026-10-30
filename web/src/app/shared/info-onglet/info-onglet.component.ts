// UbiFleet — Titre d'onglet avec bouton « info » : le texte descriptif de
// l'onglet (contenu projeté) ne s'affiche qu'au clic.
import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';

@Component({
  selector: 'ubi-info-onglet',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="io-titre">
      <h2>@if (icone()) { <i [class]="icone()"></i> }{{ titre() }}</h2>
      <button type="button" class="io-btn" [class.actif]="ouvert()" [attr.aria-expanded]="ouvert()"
              [title]="ouvert() ? 'Masquer l\\'explication' : 'Comment lire cet onglet ?'" (click)="ouvert.set(!ouvert())">
        <i class="fas fa-info-circle"></i>
      </button>
    </div>
    @if (ouvert()) {
      <div class="io-panneau" role="note">
        <ng-content />
        <button type="button" class="io-fermer" title="Fermer" (click)="ouvert.set(false)"><i class="fas fa-times"></i></button>
      </div>
    }
  `,
  styles: [`
    :host { display: block; margin-bottom: 12px; }
    .io-titre { display: flex; align-items: center; gap: 8px; }
    h2 { margin: 0; font-size: 17px; color: var(--navy); i { color: var(--green-dark); margin-right: 6px; } }
    .io-btn {
      position: relative; display: inline-flex; align-items: center; justify-content: center;
      width: 26px; height: 26px; border-radius: 50%; border: 1.5px solid var(--gray-300, #cbd5e1);
      background: white; color: var(--info, #3b82f6); cursor: pointer; font-size: 14px;
      &:hover, &.actif { border-color: var(--info, #3b82f6); background: var(--info-light, #eff6ff); }
    }
    .io-panneau {
      position: relative; margin-top: 8px; padding: 12px 36px 12px 14px; max-width: 920px;
      border-radius: var(--radius-md); background: var(--info-light, #eff6ff); color: #1e3a8a;
      font-size: 12.5px; line-height: 1.55;
    }
    .io-fermer { position: absolute; top: 6px; right: 6px; border: none; background: none; cursor: pointer; color: #1e3a8a; }
  `],
})
export class InfoOngletComponent {
  titre = input.required<string>();
  icone = input<string>('');
  ouvert = signal(false);
}
