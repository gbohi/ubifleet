// UbiFleet — Formulaire de relevé kilométrique (création et correction)
//
// Le même formulaire partout : fiche véhicule, historique kilométrique du
// véhicule et liste globale des relevés. Sans `vehiculeId`, on choisit le
// véhicule dans la liste ; avec `releve`, on corrige un relevé existant.
import {
  ChangeDetectionStrategy, Component, OnInit, computed, effect, inject, input, output, signal,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { VehiculeApiService } from '../../core/services/api.service';
import { TypesMouvementService } from '../../core/services/types-mouvement.service';
import { FenetreSaisieService, heureLocale, messageErreurApi } from '../../core/services/fenetre-saisie.service';
import {
  OptionTournee, OptionVehicule, OptionsSaisieService, tourneesDuVehicule,
} from '../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../select-recherche/select-recherche.component';
import { ReleveKilometrage } from '../../core/models';

/** Code du type de mouvement réservé qui demande la tournée. */
export const TYPE_TOURNEE = 'tournee';

const ICONES: Record<string, string> = {
  entree: 'fa-sign-in-alt', sortie: 'fa-sign-out-alt', releve: 'fa-tachometer-alt', tournee: 'fa-route',
};

@Component({
  selector: 'ubi-releve-form',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe, SelectRechercheComponent],
  templateUrl: './releve-form.component.html',
  styleUrls: ['./releve-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReleveFormComponent implements OnInit {
  /** Véhicule imposé (fiche, historique du véhicule) ; sinon il est choisi dans la liste. */
  vehiculeId = input<string | null>(null);
  /** Relevé à corriger ; absent = nouveau relevé. */
  releve = input<ReleveKilometrage | null>(null);

  enregistre = output<ReleveKilometrage>();
  ferme      = output<void>();

  private fb          = inject(FormBuilder);
  private vehiculeApi = inject(VehiculeApiService);
  private options     = inject(OptionsSaisieService);
  readonly typesMvt   = inject(TypesMouvementService);
  readonly fenetres   = inject(FenetreSaisieService);

  vehicules  = signal<OptionVehicule[]>([]);
  chauffeurs = signal<OptionRecherche[]>([]);
  private tournees = signal<OptionTournee[]>([]);
  /** Véhicule imposé (chargé à part : il peut ne pas figurer dans la liste). */
  private vehiculeImpose = signal<{ immatriculation: string; km: number; agence: string | null } | null>(null);

  saving = signal(false);
  error  = signal('');
  motifCorrection = signal('');
  photoFile    = signal<File | null>(null);
  photoPreview = signal<string | null>(null);

  edition = computed(() => !!this.releve());
  /** Relevé ancien enregistré sans heure : on ne force pas à en inventer une. */
  heureFacultative = computed(() => this.edition() && !this.releve()!.heure_releve);

  form = this.fb.group({
    vehicule:       ['' as string, Validators.required],
    kilometrage:    [null as number | null, [Validators.required, Validators.min(0)]],
    date_releve:    ['', [Validators.required,
                          (c: AbstractControl) => this.fenetres.erreur('releves', c.value) ? { fenetre: true } : null]],
    heure_releve:   [null as string | null,
                     (c: AbstractControl) => !c.value && !this.heureFacultative() ? { required: true } : null],
    type_mouvement: ['releve', Validators.required],
    tournee:        [null as number | null],
    chauffeur:      [null as string | null],
    notes:          [''],
  });
  get f() { return this.form.controls; }

  private valeurs = toSignal(this.form.valueChanges, { initialValue: this.form.getRawValue() });
  typeTournee = computed(() => this.valeurs().type_mouvement === TYPE_TOURNEE);
  private dateCourante = computed(() => this.valeurs().date_releve ?? null);

  /** Bandeau : immatriculation et kilométrage actuel du véhicule. */
  vehiculeInfo = computed(() => {
    const impose = this.vehiculeImpose();
    if (impose) return impose;
    const v = this.vehicules().find(x => x.value === this.valeurs().vehicule);
    return v ? { immatriculation: v.label, km: v.km, agence: v.agence } : null;
  });
  tourneesProposees = computed(() => tourneesDuVehicule(this.tournees(), this.vehiculeInfo()?.agence));

  /** Motif obligatoire : relevé sorti de la fenêtre, ou nouvelle date hors fenêtre. */
  motifRequis = computed(() => this.edition()
    && (!!this.releve()!.hors_fenetre || this.fenetres.horsDelai('releves', this.dateCourante())));

  constructor() {
    // Bornes et heure du serveur reçues : revalider la date, pré-remplir l'heure d'un nouveau relevé
    effect(() => {
      const fen = this.fenetres.fenetre('releves');
      if (!fen) return;
      const date = this.f.date_releve, heure = this.f.heure_releve;
      if (!this.edition()) {
        if (!date.dirty) date.setValue(fen.date_max);
        if (!heure.dirty) heure.setValue(this.fenetres.heureServeur() ?? heure.value);
      }
      date.updateValueAndValidity();
    });
    // Tournée obligatoire pour le type « tournée », vidée et masquée pour les autres
    effect(() => {
      const t = this.f.tournee;
      if (this.typeTournee()) {
        t.setValidators(Validators.required);
      } else {
        t.clearValidators();
        if (t.value !== null) t.setValue(null, { emitEvent: false });
      }
      t.updateValueAndValidity({ emitEvent: false });
    });
  }

  ngOnInit(): void {
    this.typesMvt.charger();
    this.fenetres.charger();
    this.options.chauffeurs().subscribe({ next: l => this.chauffeurs.set(l), error: () => {} });
    this.options.tournees().subscribe({ next: l => this.tournees.set(l), error: () => {} });

    const r = this.releve();
    const vehicule = this.vehiculeId() ?? r?.vehicule ?? null;
    if (vehicule) {
      this.f.vehicule.setValue(vehicule);
      this.vehiculeApi.getById(vehicule).subscribe({
        next: (v: any) => this.vehiculeImpose.set({
          immatriculation: v.immatriculation, km: v.kilometrage_actuel, agence: v.agence ?? null,
        }),
        error: () => {},
      });
    } else {
      this.options.vehicules().subscribe({ next: l => this.vehicules.set(l), error: () => {} });
    }

    if (r) {
      this.form.patchValue({
        kilometrage:    r.kilometrage,
        date_releve:    r.date_releve,
        heure_releve:   r.heure_releve ? r.heure_releve.substring(0, 5) : null,
        type_mouvement: r.type_mouvement,
        tournee:        r.tournee ?? null,
        chauffeur:      r.chauffeur ?? null,
        notes:          r.notes ?? '',
      });
    } else {
      this.form.patchValue({
        date_releve:  this.fenetres.max('releves') ?? new Date().toISOString().split('T')[0],
        heure_releve: this.fenetres.heureServeur() ?? heureLocale(),
      });
    }
  }

  dateErreur(): string | null { return this.fenetres.erreur('releves', this.f.date_releve.value); }
  icone(code: string): string { return ICONES[code] ?? 'fa-circle'; }
  invalide(champ: keyof typeof this.form.controls): boolean {
    const c = this.f[champ];
    return c.invalid && c.touched;
  }

  onPhotoChange(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.photoFile.set(file);
    this.photoPreview.set(null);
    if (file) {
      const reader = new FileReader();
      reader.onload = e => this.photoPreview.set(e.target?.result as string);
      reader.readAsDataURL(file);
    }
  }

  enregistrer(): void {
    if (this.saving()) return;
    if (this.form.invalid || (this.motifRequis() && !this.motifCorrection().trim())) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set('');

    const v = this.form.getRawValue();
    const payload: Record<string, any> = {
      vehicule:       v.vehicule,
      kilometrage:    v.kilometrage,
      date_releve:    v.date_releve,
      type_mouvement: v.type_mouvement,
      tournee:        this.typeTournee() ? v.tournee : null,
      chauffeur:      v.chauffeur || null,
      notes:          v.notes || '',
    };
    if (v.heure_releve) payload['heure_releve'] = v.heure_releve;
    if (this.photoFile()) payload['photo_tableau_bord'] = this.photoFile();
    if (this.edition() && this.motifCorrection().trim()) payload['motif_correction'] = this.motifCorrection().trim();

    const req = this.edition()
      ? this.vehiculeApi.updateReleveKm(this.releve()!.id, payload)
      : this.vehiculeApi.createReleveKm(payload as any);
    req.subscribe({
      next: (r) => { this.saving.set(false); this.enregistre.emit(r); },
      error: (err) => {
        this.saving.set(false);
        this.error.set(messageErreurApi(err, "Erreur lors de l'enregistrement."));
      },
    });
  }
}
