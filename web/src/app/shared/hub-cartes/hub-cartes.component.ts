// UbiFleet — Accueil en cartes regroupées par thème (Paramètres, Rapports…)
//
// Chaque carte ouvre une rubrique ; une recherche filtre les cartes sur le
// titre, la description et le thème. Prévu pour grandir avec l'application :
// on ajoute une carte dans la liste du composant parent.
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';

export interface CarteHub { cle: string; libelle: string; description: string; icone: string; }
export interface GroupeHub {
  titre: string; icone: string;
  /** Teinte des pastilles d'icône : vert, bleu, orange, rouge, violet, gris. */
  teinte: 'vert' | 'bleu' | 'orange' | 'rouge' | 'violet' | 'gris';
  cartes: CarteHub[];
}

@Component({
  selector: 'ubi-hub-cartes',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="hub-tete">
      <div class="hub-titre">
        <span class="hub-titre-ico"><i [class]="icone()"></i></span>
        <div>
          <h1>{{ titre() }}</h1>
          <p>{{ sousTitre() }}</p>
        </div>
      </div>
      <label class="hub-recherche">
        <i class="fas fa-search"></i>
        <input type="search" [placeholder]="placeholder()" [value]="recherche()"
               (input)="recherche.set($any($event.target).value)" />
      </label>
    </div>

    @for (g of groupesFiltres(); track g.titre) {
      <section class="hub-groupe">
        <h2><i [class]="g.icone"></i> {{ g.titre }}</h2>
        <div class="hub-grille">
          @for (c of g.cartes; track c.cle) {
            <button type="button" class="hub-carte" (click)="choisir.emit(c.cle)">
              <span class="hub-ico" [class]="'t-' + g.teinte"><i [class]="c.icone"></i></span>
              <span class="hub-texte">
                <span class="hub-libelle">{{ c.libelle }}</span>
                <span class="hub-desc">{{ c.description }}</span>
              </span>
              @if (compteurs()[c.cle] !== undefined) { <span class="hub-compte">{{ compteurs()[c.cle] }}</span> }
            </button>
          }
        </div>
      </section>
    } @empty {
      <p class="hub-vide">Aucune rubrique ne correspond à « {{ recherche() }} ».</p>
    }
  `,
  styles: [`
    :host { display: block; }
    .hub-tete { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
                flex-wrap: wrap; margin-bottom: 22px; }
    .hub-titre { display: flex; gap: 12px; align-items: center;
      h1 { font-family: var(--font-display); font-size: 24px; color: var(--navy); margin: 0; }
      p { margin: 2px 0 0; color: var(--gray-500); font-size: 13px; } }
    .hub-titre-ico { width: 40px; height: 40px; border-radius: 10px; background: var(--green-alpha, #5bd98822);
                     color: var(--green-dark, #2f9e5b); display: grid; place-items: center; font-size: 17px; }
    .hub-recherche { display: flex; align-items: center; gap: 8px; width: 300px; max-width: 100%; height: 38px;
      padding: 0 12px; background: var(--white, #fff); border: 1.5px solid var(--gray-200); border-radius: 10px;
      i { color: var(--gray-400); font-size: 13px; }
      input { border: none; outline: none; flex: 1; font-size: 13px; background: transparent; font-family: inherit; } }
    .hub-groupe { margin-bottom: 22px;
      h2 { font-family: var(--font-body); font-size: 11px; font-weight: 700; letter-spacing: .6px; text-transform: uppercase; color: var(--gray-500);
           margin: 0 0 10px; display: flex; align-items: center; gap: 6px; } }
    .hub-grille { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
    .hub-carte { position: relative; display: flex; gap: 12px; align-items: flex-start; text-align: left;
      padding: 14px 14px; min-height: 76px; background: var(--white, #fff); border: 1px solid var(--gray-100);
      border-radius: 12px; cursor: pointer; font-family: inherit; box-shadow: 0 1px 2px rgba(9, 36, 64, .04);
      transition: border-color .15s, box-shadow .15s, transform .15s;
      &:hover, &:focus-visible { border-color: var(--green, #5bd988); box-shadow: 0 4px 14px rgba(9, 36, 64, .08);
                                  transform: translateY(-1px); outline: none; } }
    .hub-ico { flex-shrink: 0; width: 36px; height: 36px; border-radius: 9px; display: grid; place-items: center; font-size: 15px;
      &.t-vert   { background: #e8f8ef; color: #2f9e5b; }
      &.t-bleu   { background: #e8f0fb; color: #2f6db5; }
      &.t-orange { background: #fdf2e3; color: #c97a12; }
      &.t-rouge  { background: #fde9e7; color: #c8453a; }
      &.t-violet { background: #f1ebfb; color: #7a4fc4; }
      &.t-gris   { background: #eef1f5; color: #52627a; } }
    .hub-texte { display: flex; flex-direction: column; gap: 3px; min-width: 0; padding-right: 22px; }
    .hub-libelle { font-weight: 700; font-size: 14px; color: var(--navy); }
    .hub-desc { font-size: 12px; color: var(--gray-500); line-height: 1.4; }
    .hub-compte { position: absolute; top: 10px; right: 10px; min-width: 20px; height: 20px; padding: 0 6px;
                  border-radius: 10px; background: var(--gray-100); color: var(--gray-500); font-size: 11px;
                  font-weight: 700; display: grid; place-items: center; }
    .hub-vide { color: var(--gray-500); font-size: 13px; }
    @media (max-width: 600px) { .hub-recherche { width: 100%; } .hub-grille { grid-template-columns: 1fr; } }
  `],
})
export class HubCartesComponent {
  titre = input.required<string>();
  sousTitre = input('');
  icone = input('fas fa-cog');
  placeholder = input('Chercher…');
  groupes = input.required<GroupeHub[]>();
  compteurs = input<Record<string, number | undefined>>({});
  choisir = output<string>();

  recherche = signal('');
  groupesFiltres = computed(() => {
    const q = this.normaliser(this.recherche());
    if (!q) return this.groupes();
    return this.groupes()
      .map(g => ({ ...g, cartes: g.cartes.filter(c =>
        this.normaliser(`${g.titre} ${c.libelle} ${c.description}`).includes(q)) }))
      .filter(g => g.cartes.length);
  });

  private normaliser(s: string): string {
    return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
  }
}
