// UbiFleet — Journal des corrections d'un plein ou d'un relevé
// (qui, quand, valeurs avant / après, motif).
import { Component, ChangeDetectionStrategy, OnChanges, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ParametrageApiService } from '../../core/services/api.service';

@Component({
  selector: 'ubi-historique-corrections',
  standalone: true,
  imports: [DatePipe],
  template: `
    @if (chargement()) {
      <div class="hc-vide"><i class="fas fa-circle-notch fa-spin"></i></div>
    } @else if (corrections().length === 0) {
      <div class="hc-vide">Aucune correction : la saisie n'a jamais été modifiée.</div>
    } @else {
      <ol class="hc-liste">
        @for (c of corrections(); track c.id) {
          <li class="hc-item" [class.suppression]="c.action === 'suppression'">
            <div class="hc-entete">
              <strong>{{ c.action_display }}</strong>
              @if (c.hors_delai) { <span class="badge badge-warning">Hors délai</span> }
              <span class="hc-meta">{{ c.date | date:'dd/MM/yyyy HH:mm' }} · {{ c.auteur_nom || '—' }}</span>
            </div>
            @if (c.motif) { <div class="hc-motif"><i class="fas fa-comment-alt"></i> {{ c.motif }}</div> }
            @if (c.changements?.length) {
              <table class="hc-table">
                @for (x of c.changements; track x.champ) {
                  <tr>
                    <th>{{ x.libelle }}</th>
                    <td class="hc-avant">{{ x.avant ?? '—' }}</td>
                    @if (c.action === 'modification') {
                      <td class="hc-fleche"><i class="fas fa-arrow-right"></i></td>
                      <td class="hc-apres">{{ x.apres ?? '—' }}</td>
                    }
                  </tr>
                }
              </table>
            }
          </li>
        }
      </ol>
    }
  `,
  styles: [`
    :host { display: block; }
    .hc-vide { padding: 14px 0; font-size: 13px; color: var(--gray-400); }
    .hc-liste { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
    .hc-item { border-left: 3px solid var(--info); background: var(--gray-50); border-radius: 8px; padding: 10px 12px; }
    .hc-item.suppression { border-left-color: var(--danger); }
    .hc-entete { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 13px; color: var(--navy); }
    .hc-meta { margin-left: auto; font-size: 12px; color: var(--gray-500); }
    .hc-motif { margin-top: 6px; font-size: 12.5px; color: var(--gray-700); i { color: var(--gray-400); margin-right: 4px; } }
    .hc-table { margin-top: 8px; width: 100%; border-collapse: collapse; font-size: 12.5px; table-layout: fixed; }
    .hc-table th { text-align: left; font-weight: 600; color: var(--gray-500); width: 34%; padding: 3px 6px 3px 0; vertical-align: top; }
    .hc-table td { padding: 3px 4px; overflow-wrap: anywhere; vertical-align: top; }
    .hc-avant { color: var(--gray-500); text-decoration: line-through; }
    .hc-apres { color: var(--navy); font-weight: 600; }
    .hc-fleche { width: 22px; color: var(--gray-300); text-align: center; }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HistoriqueCorrectionsComponent implements OnChanges {
  private api = inject(ParametrageApiService);

  domaine = input.required<'carburant' | 'releves'>();
  objet   = input.required<string>();

  corrections = signal<any[]>([]);
  chargement  = signal(true);

  ngOnChanges(): void {
    this.chargement.set(true);
    this.api.getCorrections({ domaine: this.domaine(), objet: this.objet() }).subscribe({
      next: l => { this.corrections.set(l); this.chargement.set(false); },
      error: () => { this.corrections.set([]); this.chargement.set(false); },
    });
  }
}
