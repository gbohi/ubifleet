// UbiFleet — Paramètres › Échéances et Carburant & consommation
//
// Un couple de seuils (attention / urgent) par échéance, utilisé à la fois
// par l'État du parc (couleurs) et par les alertes (priorité).
import {
  Component, ChangeDetectionStrategy, OnInit, computed, inject, input, signal,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { ParametrageApiService } from '../../../core/services/api.service';

interface Echeance { code: string; libelle: string; unite: 'jours' | 'km'; }

const ECHEANCES: Echeance[] = [
  { code: 'assurance',       libelle: 'Assurance',          unite: 'jours' },
  { code: 'ct',              libelle: 'Contrôle technique', unite: 'jours' },
  { code: 'carte_transport', libelle: 'Carte de transport', unite: 'jours' },
  { code: 'vignette',        libelle: 'Vignette',           unite: 'jours' },
  { code: 'permis',          libelle: 'Permis de conduire', unite: 'jours' },
  { code: 'revision',        libelle: 'Révision',           unite: 'km' },
  { code: 'pneus',           libelle: 'Pneus',              unite: 'km' },
];

const AUTRES_CLES = ['conso_anomalie_pct', 'prix_carburant_litre'];

@Component({
  selector: 'ubi-param-seuils',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe],
  templateUrl: './seuils.component.html',
  styleUrls: ['./seuils.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SeuilsComponent implements OnInit {
  private api = inject(ParametrageApiService);

  /** Rubrique affichée : les deux partagent le même formulaire et la même barre d'enregistrement. */
  vue      = input<'echeances' | 'carburant'>('echeances');
  ecriture = input(true);

  readonly groupes = [
    { titre: 'Documents véhicule', icone: 'fas fa-file-alt',
      aide: "Jours restants avant la date d'expiration du document le plus récent.",
      echeances: ECHEANCES.filter(e => ['assurance', 'ct', 'carte_transport', 'vignette'].includes(e.code)) },
    { titre: 'Chauffeurs', icone: 'fas fa-id-card',
      aide: "Jours restants avant l'expiration du permis de conduire.",
      echeances: ECHEANCES.filter(e => e.code === 'permis') },
    { titre: 'Kilométrage', icone: 'fas fa-tachometer-alt',
      aide: 'Kilomètres restants avant la révision ou le remplacement des pneus prévus.',
      echeances: ECHEANCES.filter(e => ['revision', 'pneus'].includes(e.code)) },
  ];

  form = new FormGroup<Record<string, FormControl<number | null>>>(
    Object.fromEntries([
      ...ECHEANCES.flatMap(e => [`echeance_${e.code}_attention`, `echeance_${e.code}_urgent`]),
      ...AUTRES_CLES,
    ].map(cle => [cle, new FormControl<number | null>(null, [Validators.required, Validators.min(1)])]))
  );

  private valeurs   = toSignal(this.form.valueChanges, { initialValue: this.form.value });
  private initiales = signal<Record<string, number | null>>({});

  chargement   = signal(true);
  enregistrement = signal(false);
  notice       = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);

  modifiees = computed(() => {
    const v = this.valeurs(), init = this.initiales();
    return Object.keys(v).filter(k => Number(v[k]) !== Number(init[k]));
  });

  incoherences = computed(() => {
    const v = this.valeurs();
    return ECHEANCES
      .filter(e => {
        const att = Number(v[`echeance_${e.code}_attention`]);
        const urg = Number(v[`echeance_${e.code}_urgent`]);
        return att > 0 && urg > 0 && att <= urg;
      })
      .map(e => e.code);
  });

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.chargement.set(true);
    this.api.getAll('alertes').subscribe({
      next: list => {
        const vals: Record<string, number | null> = {};
        Object.keys(this.form.controls).forEach(k => vals[k] = null);
        list.forEach((p: any) => { if (p.cle in vals) vals[p.cle] = Number(p.valeur); });
        this.initiales.set(vals);
        this.form.reset(vals);
        if (!this.ecriture()) this.form.disable();
        this.chargement.set(false);
      },
      error: () => {
        this.chargement.set(false);
        this.notice.set({ type: 'err', texte: 'Impossible de charger les paramètres.' });
      },
    });
  }

  val(cle: string): number | null { return this.valeurs()[cle] ?? null; }
  modifie(cle: string): boolean { return this.modifiees().includes(cle); }
  incoherent(code: string): boolean { return this.incoherences().includes(code); }

  annuler(): void {
    this.form.reset(this.initiales());
    this.notice.set(null);
  }

  enregistrer(): void {
    if (this.form.invalid || this.incoherences().length || this.enregistrement()) return;
    const items = this.modifiees().map(cle => ({ cle, valeur: String(this.valeurs()[cle]) }));
    if (!items.length) return;
    this.enregistrement.set(true);
    this.notice.set(null);
    this.api.bulkUpdate(items).subscribe({
      next: () => {
        this.enregistrement.set(false);
        this.notice.set({ type: 'ok', texte: 'Seuils enregistrés. Ils s’appliquent à l’État du parc et aux prochaines alertes.' });
        this.charger();
      },
      error: (err: any) => {
        this.enregistrement.set(false);
        this.notice.set({ type: 'err', texte: err?.error?.detail ?? "Erreur lors de l'enregistrement." });
      },
    });
  }
}
