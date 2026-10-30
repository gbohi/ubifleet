// UbiFleet — Filtres communs des analyses carburant (période, agence,
// véhicule et chauffeur avec recherche, type de mouvement).
import { ChangeDetectionStrategy, Component, OnInit, inject, input, output, signal } from '@angular/core';
import { OptionVehicule, OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { Agence } from '../../../core/models';

export interface FiltresAnalyse {
  date_debut: string; date_fin: string;
  agence?: string; vehicule?: string; chauffeur?: string; type_mouvement?: string;
}

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Période par défaut : début du mois, il y a `mois` mois, jusqu'à aujourd'hui. */
export function periodeParDefaut(mois = 2): { debut: string; fin: string } {
  const n = new Date();
  return { debut: iso(new Date(n.getFullYear(), n.getMonth() - mois, 1)), fin: iso(n) };
}

@Component({
  selector: 'ubi-filtres-analyse',
  standalone: true,
  imports: [SelectRechercheComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="fa">
      <div class="fa-champ"><label for="fa-debut">Du *</label>
        <input id="fa-debut" type="date" class="form-control" [value]="debut()" (change)="debut.set($any($event.target).value)" /></div>
      <div class="fa-champ"><label for="fa-fin">Au *</label>
        <input id="fa-fin" type="date" class="form-control" [value]="fin()" (change)="fin.set($any($event.target).value)" /></div>
      @if (agences().length > 1) {
        <div class="fa-champ"><label for="fa-agence">Agence</label>
          <select id="fa-agence" class="form-control" [value]="agence()" (change)="agence.set($any($event.target).value)">
            <option value="">Toutes</option>
            @for (a of agences(); track a.id) { <option [value]="a.id">{{ a.nom }}</option> }
          </select></div>
      }
      <div class="fa-champ fa-large"><label>Véhicule</label>
        <ubi-select-recherche placeholder="Immatriculation…" [options]="vehicules()" [selection]="vehicule()"
                              (choix)="vehicule.set($event ?? '')" /></div>
      @if (avecChauffeur()) {
        <div class="fa-champ fa-large"><label>Chauffeur</label>
          <ubi-select-recherche placeholder="Matricule ou nom…" [options]="chauffeurs()" [selection]="chauffeur()"
                                (choix)="chauffeur.set($event ?? '')" /></div>
      }
      @if (avecType()) {
        <div class="fa-champ"><label for="fa-type">Type de mouvement</label>
          <select id="fa-type" class="form-control" [value]="type()" (change)="type.set($any($event.target).value)">
            <option value="">Tous</option>
            @for (t of typesMvt.tous(); track t.code) { @if (t.pour_prises) { <option [value]="t.code">{{ t.libelle }}</option> } }
          </select></div>
      }
      <div class="fa-actions">
        <button class="btn btn-green" [disabled]="chargement() || !debut() || !fin()" (click)="emettre()">
          <i class="fas" [class.fa-search]="!chargement()" [class.fa-circle-notch]="chargement()" [class.fa-spin]="chargement()"></i> Afficher
        </button>
        <ng-content />
      </div>
    </div>
  `,
  styles: [`
    .fa { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; padding: 14px; margin-bottom: 14px;
          background: white; border: 1px solid var(--gray-200); border-radius: var(--radius-lg); }
    .fa-champ { display: flex; flex-direction: column; gap: 4px; flex: 1 1 140px; min-width: 140px; max-width: 200px;
      label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; color: var(--gray-500); } }
    .fa-large { max-width: 240px; flex-basis: 190px; }
    .fa-actions { display: flex; gap: 6px; margin-left: auto; flex-wrap: wrap; }
  `],
})
export class FiltresAnalyseComponent implements OnInit {
  agences = input<Agence[]>([]);
  avecType = input(true);
  avecChauffeur = input(true);
  chargement = input(false);
  /** Période proposée : depuis le début du mois, il y a N mois (0 = mois en cours). */
  moisPrecedents = input(2);
  appliquer = output<FiltresAnalyse>();

  private options = inject(OptionsSaisieService);
  readonly typesMvt = inject(TypesMouvementService);

  debut = signal(periodeParDefaut().debut);
  fin = signal(periodeParDefaut().fin);
  agence = signal('');
  vehicule = signal('');
  chauffeur = signal('');
  type = signal('');
  vehicules = signal<OptionVehicule[]>([]);
  chauffeurs = signal<OptionRecherche[]>([]);

  ngOnInit(): void {
    const p = periodeParDefaut(this.moisPrecedents());
    this.debut.set(p.debut);
    this.fin.set(p.fin);
    this.typesMvt.charger();
    this.options.vehicules().subscribe({ next: l => this.vehicules.set(l), error: () => {} });
    if (this.avecChauffeur()) this.options.chauffeurs(true).subscribe({ next: l => this.chauffeurs.set(l), error: () => {} });
    this.emettre();
  }

  emettre(): void {
    const f: FiltresAnalyse = { date_debut: this.debut(), date_fin: this.fin() };
    if (this.agence()) f.agence = this.agence();
    if (this.vehicule()) f.vehicule = this.vehicule();
    if (this.chauffeur() && this.avecChauffeur()) f.chauffeur = this.chauffeur();
    if (this.type() && this.avecType()) f.type_mouvement = this.type();
    this.appliquer.emit(f);
  }
}

/** Téléchargement CSV lisible par Excel (séparateur « ; », virgule décimale). */
export function exporterCsv(nom: string, entetes: string[], lignes: any[][]): void {
  const cellule = (v: any) => {
    const t = v === null || v === undefined ? '' : typeof v === 'number' ? String(v).replace('.', ',') : String(v);
    return `"${t.replace(/"/g, '""').replace(/\s+/g, ' ')}"`;
  };
  const csv = '﻿' + [entetes, ...lignes].map(r => r.map(cellule).join(';')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  a.download = nom;
  a.click();
  URL.revokeObjectURL(a.href);
}
