// UbiFleet — Liste déroulante avec recherche à la saisie
//
// Remplace un <select> quand la liste est longue (véhicules, chauffeurs,
// tournées, stations) : on tape quelques caractères et la liste se filtre
// (sans tenir compte des accents ni de la casse). S'utilise comme un champ
// de formulaire (formControlName / ngModel) ; la valeur est `value` de l'option.
import {
  ChangeDetectionStrategy, Component, ElementRef, HostListener, computed, forwardRef,
  inject, input, signal, viewChild,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface OptionRecherche {
  value: string | number;
  label: string;
  /** Complément affiché en petit et inclus dans la recherche (désignation, agence…). */
  detail?: string;
}

const MAX_AFFICHES = 50;

const normaliser = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

@Component({
  selector: 'ubi-select-recherche',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => SelectRechercheComponent), multi: true }],
  template: `
    <div class="sr" [class.sr-ouvert]="ouvert()">
      <input #champ type="text" class="form-control sr-champ" autocomplete="off"
             [id]="inputId()" [placeholder]="placeholder()" [disabled]="desactive()"
             [class.is-invalid]="invalid()"
             role="combobox" [attr.aria-expanded]="ouvert()" aria-autocomplete="list"
             [value]="texte()" (input)="saisir($any($event.target).value)"
             (focus)="ouvrir()" (click)="ouvrir()" (keydown)="clavier($event)" (blur)="quitter()" />
      @if (valeur() !== null && !desactive()) {
        <button type="button" class="sr-effacer" title="Effacer" tabindex="-1"
                (mousedown)="$event.preventDefault()" (click)="choisir(null)">
          <i class="fas fa-times"></i>
        </button>
      } @else {
        <i class="fas fa-chevron-down sr-fleche"></i>
      }
      @if (ouvert()) {
        <ul class="sr-liste" role="listbox">
          @for (o of affichees(); track o.value; let i = $index) {
            <li role="option" class="sr-option" [class.sr-actif]="i === actif()"
                [class.sr-choisi]="o.value === valeur()" [attr.aria-selected]="o.value === valeur()"
                (mousedown)="$event.preventDefault(); choisir(o)" (mouseenter)="actif.set(i)">
              <span class="sr-label">{{ o.label }}</span>
              @if (o.detail) { <span class="sr-detail">{{ o.detail }}</span> }
            </li>
          } @empty {
            <li class="sr-vide">{{ options().length ? 'Aucun résultat pour « ' + recherche() + ' »' : 'Aucune option disponible' }}</li>
          }
          @if (filtrees().length > affichees().length) {
            <li class="sr-vide">{{ filtrees().length - affichees().length }} autre(s) : précisez la recherche.</li>
          }
        </ul>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }
    .sr { position: relative; }
    .sr-champ { padding-right: 32px; }
    .sr-fleche, .sr-effacer {
      position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
      color: var(--gray-400); font-size: 11px;
    }
    .sr-fleche { pointer-events: none; }
    .sr-effacer { border: none; background: none; cursor: pointer; padding: 4px; }
    .sr-effacer:hover { color: var(--danger, #c0392b); }
    .sr-liste {
      position: absolute; z-index: 60; left: 0; right: 0; top: calc(100% + 4px);
      max-height: 260px; overflow-y: auto; margin: 0; padding: 4px 0; list-style: none;
      background: var(--white, #fff); border: 1px solid var(--gray-200); border-radius: var(--radius-md, 8px);
      box-shadow: 0 8px 24px rgba(9, 36, 64, .12);
    }
    .sr-option { padding: 8px 12px; cursor: pointer; display: flex; flex-direction: column; gap: 1px; }
    .sr-option.sr-actif { background: var(--gray-50); }
    .sr-option.sr-choisi .sr-label { font-weight: 700; color: var(--navy); }
    .sr-label { font-size: 13px; color: var(--gray-700, #333); }
    .sr-detail { font-size: 11px; color: var(--gray-400); }
    .sr-vide { padding: 8px 12px; font-size: 12px; color: var(--gray-400); }
  `],
})
export class SelectRechercheComponent implements ControlValueAccessor {
  options     = input<OptionRecherche[]>([]);
  placeholder = input('Rechercher…');
  invalid     = input(false);
  inputId     = input<string | null>(null);

  private hote = inject(ElementRef<HTMLElement>);
  private champ = viewChild<ElementRef<HTMLInputElement>>('champ');

  valeur     = signal<string | number | null>(null);
  desactive  = signal(false);
  ouvert     = signal(false);
  /** Texte tapé ; null = afficher le libellé de l'option choisie. */
  recherche  = signal<string | null>(null);
  actif      = signal(0);

  private choisie = computed(() => this.options().find(o => o.value === this.valeur()) ?? null);
  texte = computed(() => this.recherche() ?? this.choisie()?.label ?? '');

  filtrees = computed(() => {
    const q = normaliser((this.recherche() ?? '').trim());
    if (!q) return this.options();
    const mots = q.split(/\s+/);
    return this.options().filter(o => {
      const t = normaliser(`${o.label} ${o.detail ?? ''}`);
      return mots.every(m => t.includes(m));
    });
  });
  affichees = computed(() => this.filtrees().slice(0, MAX_AFFICHES));

  private onChange: (v: any) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(v: any): void { this.valeur.set(v === '' || v === undefined ? null : v); this.recherche.set(null); }
  registerOnChange(fn: (v: any) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void { this.onTouched = fn; }
  setDisabledState(d: boolean): void { this.desactive.set(d); if (d) this.ouvert.set(false); }

  ouvrir(): void {
    if (this.desactive() || this.ouvert()) return;
    const i = this.filtrees().findIndex(o => o.value === this.valeur());
    this.actif.set(Math.max(0, i));
    this.ouvert.set(true);
  }

  saisir(t: string): void {
    this.recherche.set(t);
    this.actif.set(0);
    this.ouvert.set(true);
  }

  choisir(o: OptionRecherche | null): void {
    const v = o ? o.value : null;
    this.recherche.set(null);
    this.ouvert.set(false);
    if (v !== this.valeur()) { this.valeur.set(v); this.onChange(v); }
    this.onTouched();
    if (!o) this.champ()?.nativeElement.focus();
  }

  /** Sortie du champ : un texte qui ne correspond à aucune option est abandonné. */
  quitter(): void {
    this.ouvert.set(false);
    this.recherche.set(null);
    this.onTouched();
  }

  clavier(e: KeyboardEvent): void {
    const n = this.affichees().length;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (!this.ouvert()) { this.ouvrir(); return; }
        this.actif.set(n ? (this.actif() + 1) % n : 0);
        this.defiler();
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.actif.set(n ? (this.actif() - 1 + n) % n : 0);
        this.defiler();
        break;
      case 'Enter':
        if (this.ouvert()) {
          e.preventDefault();
          const o = this.affichees()[this.actif()];
          if (o) this.choisir(o);
        }
        break;
      case 'Escape':
        if (this.ouvert()) { e.preventDefault(); e.stopPropagation(); this.quitter(); }
        break;
      case 'Tab':
        // Tab valide l'option en surbrillance si l'utilisateur a tapé une recherche
        if (this.ouvert() && this.recherche()) {
          const o = this.affichees()[this.actif()];
          if (o) this.choisir(o);
        }
        break;
    }
  }

  private defiler(): void {
    queueMicrotask(() => this.hote.nativeElement.querySelector('.sr-actif')?.scrollIntoView({ block: 'nearest' }));
  }

  @HostListener('document:touchstart', ['$event'])
  toucherDehors(e: Event): void {
    if (this.ouvert() && !this.hote.nativeElement.contains(e.target as Node)) this.quitter();
  }
}
