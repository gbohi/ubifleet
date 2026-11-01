// UbiFleet — Paramètres : référentiel simple (code, libellé, ordre, actif)
//
// Écran commun des listes paramétrables à code (types de véhicule, catégories
// de dépense, types de sinistre / contrat…) : recherche, création, modification, activation, suppression
// (refusée par le serveur si l'élément est utilisé), export.
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { environment } from '@env/environment';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';

interface Element {
  id: number; code: string; libelle: string; ordre: number; actif: boolean; nb_utilisations: number;
  /** Élément utilisé par l'application : ni suppression ni désactivation. */
  systeme?: boolean;
  [cle: string]: any;
}

/** Champ supplémentaire à liste de choix (ex. poste du budget d'une catégorie de dépense). */
export interface ChampChoix { cle: string; libelle: string; options: { value: string; label: string }[]; aide?: string; }

@Component({
  selector: 'ubi-referentiel-simple',
  standalone: true,
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['../parametres.component.scss'],
  template: `
    <section class="p-panel">
      <div class="p-head">
        <div>
          <h2>{{ titre() }} <span class="p-chip">{{ elements().length }}</span></h2>
          <p>{{ description() }}</p>
          @if (utiliseDans().length) {
            <div class="p-used-in">@for (u of utiliseDans(); track u; let i = $index) {
              <span class="p-chip">{{ i === 0 ? 'Utilisé dans : ' : '' }}{{ u }}</span> }</div>
          }
        </div>
        <div class="p-actions">
          <input class="p-search" placeholder="Rechercher…" [value]="recherche()" (input)="recherche.set($any($event.target).value)" />
          <button class="btn btn-outline btn-sm" (click)="exporter()"><i class="fas fa-file-csv"></i> Exporter</button>
          @if (ecriture()) {
            <button class="btn btn-green btn-sm" (click)="ouvrir(null)"><i class="fas fa-plus"></i> {{ libelleNouveau() }}</button>
          }
        </div>
      </div>
      @if (notice()) { <div class="p-notice err" style="margin:0 0 12px"><i class="fas fa-exclamation-triangle"></i> {{ notice() }}</div> }
      <div class="p-table-wrap">
        <table class="p-table">
          <thead><tr><th class="num p-hide-m">Ordre</th><th>Libellé</th><th class="p-hide-m">Code</th>
            @for (c of champs(); track c.cle) { <th class="p-hide-m">{{ c.libelle }}</th> }
            <th class="num">{{ colonneUtilisations() }}</th><th class="p-col-toggle">Actif</th><th class="p-col-actions"></th></tr></thead>
          <tbody>
            @for (x of filtres(); track x.id) {
              <tr [class.inactif]="!x.actif">
                <td class="num muted p-hide-m">{{ x.ordre }}</td>
                <td>{{ x.libelle }}
                  @if (x.systeme) { <i class="fas fa-lock muted" title="Utilisé par l'application : ni suppression ni désactivation"></i> }</td>
                <td class="muted p-hide-m">{{ x.code }}</td>
                @for (c of champs(); track c.cle) { <td class="p-hide-m">{{ libelleChoix(c, x[c.cle]) }}</td> }
                <td class="num">{{ x.nb_utilisations }}</td>
                <td class="p-col-toggle"><button class="p-toggle" [class.on]="x.actif" [disabled]="!ecriture() || x.systeme" (click)="basculer(x)"></button></td>
                <td class="p-col-actions">
                  @if (ecriture()) {
                    <button class="p-icon-btn" title="Modifier" (click)="ouvrir(x)"><i class="fas fa-edit"></i></button>
                    @if (!x.systeme) {
                      <button class="p-icon-btn danger" [title]="x.nb_utilisations ? 'Utilisé : désactivez-le plutôt' : 'Supprimer'"
                              (click)="supprimer(x)"><i class="fas fa-trash"></i></button>
                    }
                  }
                </td>
              </tr>
            } @empty {
              <tr><td [attr.colspan]="6 + champs().length" class="p-empty">Aucun élément.</td></tr>
            }
          </tbody>
        </table>
      </div>
    </section>

    @if (edite() !== undefined) {
      <div class="modal-backdrop" (click)="edite.set(undefined)">
        <div class="modal-container" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <div class="modal-title">{{ edite() ? 'Modifier' : libelleNouveau() }}</div>
            <button class="btn-close-modal" (click)="edite.set(undefined)"><i class="fas fa-times"></i></button>
          </div>
          @if (erreur()) { <div class="p-notice err" style="margin:0 0 16px"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }
          <form [formGroup]="form" novalidate (ngSubmit)="enregistrer()">
            <div class="p-form-grid-2">
              <div class="form-group">
                <label class="form-label" for="rs-libelle">Libellé *</label>
                <input id="rs-libelle" class="form-control" formControlName="libelle" />
              </div>
              <div class="form-group">
                <label class="form-label" for="rs-code">Code *</label>
                <input id="rs-code" class="form-control" formControlName="code" />
                <small class="aide-dotation">Minuscules, chiffres, - ou _. Non modifiable ensuite.</small>
              </div>
            </div>
            @for (c of champs(); track c.cle) {
              <div class="form-group">
                <label class="form-label" [for]="'rs-' + c.cle">{{ c.libelle }} *</label>
                <select [id]="'rs-' + c.cle" class="form-control" [formControlName]="c.cle">
                  @for (o of c.options; track o.value) { <option [value]="o.value">{{ o.label }}</option> }
                </select>
                @if (c.aide) { <small class="aide-dotation">{{ c.aide }}</small> }
              </div>
            }
            <div class="p-form-grid-2">
              <div class="form-group"><label class="form-label" for="rs-ordre">Ordre d'affichage</label>
                <input id="rs-ordre" type="number" min="0" class="form-control" formControlName="ordre" /></div>
              <div class="form-group"><label class="p-check" style="margin-top:26px"><input type="checkbox" formControlName="actif" /> Actif</label>
                @if (edite()?.systeme) { <small class="aide-dotation">Utilisé par l'application : reste actif.</small> }</div>
            </div>
            <div class="p-modal-actions">
              <button type="button" class="btn btn-outline" (click)="edite.set(undefined)">Annuler</button>
              <button type="submit" class="btn btn-green" [disabled]="form.invalid"><i class="fas fa-save"></i> Enregistrer</button>
            </div>
          </form>
        </div>
      </div>
    }
  `,
})
export class ReferentielSimpleComponent implements OnInit {
  /** Chemin sous /parametrage/ (ex. « types-vehicule »). */
  ressource = input.required<string>();
  titre = input.required<string>();
  description = input('');
  utiliseDans = input<string[]>([]);
  libelleNouveau = input('Nouvel élément');
  colonneUtilisations = input('Utilisations');
  ecriture = input(false);
  /** Champs supplémentaires à liste de choix. */
  champs = input<ChampChoix[]>([]);
  /** Nombre d'éléments, pour le menu de la page Paramètres. */
  compte = output<number>();

  private http = inject(HttpClient);
  private fb = inject(FormBuilder);

  elements = signal<Element[]>([]);
  recherche = signal('');
  notice = signal('');
  erreur = signal('');
  edite = signal<Element | null | undefined>(undefined);
  filtres = computed(() => {
    const q = this.recherche().trim().toLowerCase();
    return q ? this.elements().filter(x => `${x.libelle} ${x.code}`.toLowerCase().includes(q)) : this.elements();
  });

  form: FormGroup = this.fb.group({
    libelle: ['', Validators.required],
    code: ['', [Validators.required, Validators.pattern(/^[a-z0-9_-]+$/)]],
    ordre: [0],
    actif: [true],
  });

  private get url(): string { return `${environment.apiUrl}/parametrage/${this.ressource()}/`; }

  ngOnInit(): void {
    for (const c of this.champs()) this.form.addControl(c.cle, this.fb.control(c.options[0]?.value ?? '', Validators.required));
    this.charger();
  }

  libelleChoix(c: ChampChoix, valeur: string): string {
    return c.options.find(o => o.value === valeur)?.label ?? valeur ?? '—';
  }

  charger(): void {
    this.http.get<Element[]>(this.url).subscribe({
      next: l => { this.elements.set(l); this.compte.emit(l.length); },
      error: () => this.elements.set([]),
    });
  }

  ouvrir(x: Element | null): void {
    this.erreur.set('');
    const extra = Object.fromEntries(this.champs().map(c => [c.cle, x ? x[c.cle] : (c.options[0]?.value ?? '')]));
    this.form.reset(x ? { libelle: x.libelle, code: x.code, ordre: x.ordre, actif: x.actif, ...extra }
                      : { libelle: '', code: '', ordre: this.elements().length + 1, actif: true, ...extra });
    if (x) this.form.controls['code'].disable(); else this.form.controls['code'].enable();
    if (x?.systeme) this.form.controls['actif'].disable(); else this.form.controls['actif'].enable();
    this.edite.set(x);
  }

  enregistrer(): void {
    const x = this.edite();
    const valeurs = this.form.getRawValue();
    if (x) delete valeurs.code;
    const req = x ? this.http.patch(`${this.url}${x.id}/`, valeurs)
                  : this.http.post(this.url, valeurs);
    req.subscribe({
      next: () => { this.edite.set(undefined); this.charger(); },
      error: err => this.erreur.set(messageErreurApi(err, "Erreur lors de l'enregistrement.")),
    });
  }

  basculer(x: Element): void {
    this.http.patch(`${this.url}${x.id}/`, { actif: !x.actif }).subscribe({
      next: () => this.charger(),
      error: err => this.notice.set(messageErreurApi(err, 'Modification impossible.')),
    });
  }

  supprimer(x: Element): void {
    if (!confirm(`Supprimer « ${x.libelle} » ?`)) return;
    this.notice.set('');
    this.http.delete(`${this.url}${x.id}/`).subscribe({
      next: () => this.charger(),
      error: err => this.notice.set(messageErreurApi(err, 'Suppression impossible.')),
    });
  }

  exporter(): void {
    const lignes = [['Ordre', 'Libellé', 'Code', ...this.champs().map(c => c.libelle), this.colonneUtilisations(), 'Actif'],
      ...this.elements().map(x => [x.ordre, x.libelle, x.code, ...this.champs().map(c => this.libelleChoix(c, x[c.cle])),
                                   x.nb_utilisations, x.actif ? 'oui' : 'non'])];
    const csv = '﻿' + lignes.map(l => l.map(c => `"${String(c).replace(/"/g, '""')}"`).join(';')).join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    a.download = `${this.ressource()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
}
