// UbiFleet — Vehicule Form Component (Angular 18 — Ajout & Modification)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { VehiculeApiService, AgenceApiService, ParametrageApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../../shared/select-recherche/select-recherche.component';

@Component({
  selector: 'ubi-vehicule-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, SelectRechercheComponent],
  templateUrl: './vehicule-form.component.html',
  styleUrls: ['./vehicule-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculeFormComponent implements OnInit {
  // Angular 18 : input() signal — undefined si mode création
  id = input<string | undefined>(undefined);

  private fb           = inject(FormBuilder);
  private router       = inject(Router);
  private vehiculeApi     = inject(VehiculeApiService);
  private agenceApi       = inject(AgenceApiService);
  private parametrageApi  = inject(ParametrageApiService);

  isEditMode = computed(() => !!this.id());

  agences    = signal<Agence[]>([]);
  chauffeurs = signal<OptionRecherche[]>([]);
  private options = inject(OptionsSaisieService);
  loading    = signal(false);
  saving     = signal(false);
  error      = signal('');
  success    = signal('');

  // Types de véhicule : Paramètres › Types de véhicule (actifs, et celui du véhicule modifié)
  typesVehicule = signal<{ value: string; label: string }[]>([]);

  readonly typesCarburant = [
    { value: 'diesel',     label: 'Diesel' },
    { value: 'essence',    label: 'Essence' },
    { value: 'hybride',    label: 'Hybride' },
    { value: 'electrique', label: 'Électrique' },
    { value: 'gpl',        label: 'GPL' },
  ];

  statutsVehicule  = signal<any[]>([]);
  affectationsUsage = signal<any[]>([]);
  marques          = signal<any[]>([]);
  modeles          = signal<any[]>([]);
  modelesFiltres   = signal<any[]>([]);

  readonly anneesDisponibles: number[] = (() => {
    const current = new Date().getFullYear();
    return Array.from({ length: 30 }, (_, i) => current - i);
  })();

  form = this.fb.group({
    // Identification
    immatriculation:                 ['', [Validators.required, Validators.maxLength(20)]],
    est_immatriculation_provisoire:  [false],
    numero_chassis:   [''],
    marque:           [null as number | null, Validators.required],
    modele:           [null as number | null, Validators.required],
    annee:            [new Date().getFullYear(), [Validators.required, Validators.min(1990)]],
    couleur:          [''],
    // Classification
    type_vehicule:    ['berline', Validators.required],
    type_carburant:   ['diesel',  Validators.required],
    nombre_places:    [5, [Validators.required, Validators.min(1)]],
    // Affectation
    agence:           ['', Validators.required],
    affectation:      [null as number | null],
    chauffeur_attitré: [null as string | null],
    statut:           [null as number | null],
    // Technique
    kilometrage_actuel:              [0, [Validators.required, Validators.min(0)]],
    conso_theorique_origine:   [0],
    numero_carte_carburant:    [''],
    kilometrage_revision:            [0],
    dotation_carburant_mensuelle:    [0, [Validators.min(0)]],
    // Dates
    date_mise_en_service: [''],
    date_acquisition:     [''],
    valeur_acquisition:   [null as number | null],
    // Notes
    notes: [''],
  });

  ngOnInit(): void {
    this.parametrageApi.getStatutsVehicule().subscribe({
      next: (l) => {
        this.statutsVehicule.set(l.filter((s: any) => s.actif));
        // Création : « En service » proposé par défaut (statut lu dans Paramètres › Statuts)
        if (!this.isEditMode() && !this.form.value.statut) {
          const enService = l.find((s: any) => s.code === 'en_service');
          if (enService) this.form.patchValue({ statut: enService.id });
        }
      },
      error: () => {},
    });
    this.parametrageApi.getAffectations().subscribe({
      next: (l) => this.affectationsUsage.set(l.filter((a: any) => a.actif)),
      error: () => {},
    });
    this.parametrageApi.getTypesVehicule().subscribe({
      next: (l) => this.typesVehicule.set(l
        .filter(t => t.actif || t.code === this.form.value.type_vehicule)
        .map(t => ({ value: t.code, label: t.libelle + (t.actif ? '' : ' (désactivé)') }))),
      error: () => {},
    });
    this.parametrageApi.getMarques(true).subscribe({
      next: (l) => this.marques.set(l),
      error: () => {},
    });
    this.parametrageApi.getModeles({ actif: true }).subscribe({
      next: (l) => {
        this.modeles.set(l);
        this.filtrerModeles(this.form.value.marque ?? null);
      },
      error: () => {},
    });
    // Filtrer les modèles quand la marque change
    this.form.get('marque')?.valueChanges.subscribe((marqueId) => {
      this.filtrerModeles(marqueId ?? null);
      // Réinitialiser le modèle si incohérent avec la nouvelle marque
      const modeleActuel = this.form.value.modele;
      if (modeleActuel) {
        const ok = this.modelesFiltres().some((m: any) => m.id === modeleActuel);
        if (!ok) this.form.patchValue({ modele: null }, { emitEvent: false });
      }
    });
    // Charger les agences et chauffeurs
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => {},
    });

    this.options.chauffeurs().subscribe({ next: l => this.chauffeurs.set(l), error: () => {} });

    // Mode édition : charger les données du véhicule
    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.vehiculeApi.getById(this.id()!).subscribe({
        next: (v) => {
          this.form.patchValue({
            immatriculation:                 v.immatriculation,
            est_immatriculation_provisoire:  (v as any).est_immatriculation_provisoire ?? false,
            numero_chassis:               v.numero_chassis ?? '',
            marque:                       v.marque,
            modele:                       v.modele,
            annee:                        v.annee,
            couleur:                      v.couleur,
            type_vehicule:                v.type_vehicule,
            type_carburant:               v.type_carburant,
            nombre_places:                v.nombre_places,
            agence:                       v.agence,
            affectation:                  v.affectation,
            chauffeur_attitré:            v.chauffeur_attitré,
            statut:                       v.statut,
            kilometrage_actuel:              v.kilometrage_actuel,
            conso_theorique_origine:         v.conso_theorique_origine ?? 0,
            numero_carte_carburant:          v.numero_carte_carburant ?? '',
            kilometrage_revision:             v.kilometrage_revision,
            dotation_carburant_mensuelle: Number(v.dotation_carburant_mensuelle),
            date_mise_en_service:         v.date_mise_en_service ?? '',
            date_acquisition:             v.date_acquisition ?? '',
            valeur_acquisition:           v.valeur_acquisition ?? null,
            notes:                        v.notes,
          });
          // Immatriculation et compteur ont leurs propres saisies (fiche du véhicule)
          this.form.controls.immatriculation.disable();
          this.form.controls.kilometrage_actuel.disable();
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err?.status === 0
            ? 'Serveur inaccessible.'
            : 'Impossible de charger le véhicule.');
          this.loading.set(false);
        },
      });
    }
  }

  // Getters pour les messages d'erreur dans le template
  get f() { return this.form.controls; }

  filtrerModeles(marqueId: number | null): void {
    if (!marqueId) {
      this.modelesFiltres.set([]);
      return;
    }
    this.modelesFiltres.set(this.modeles().filter((m: any) => m.marque === marqueId));
  }

  onSubmit(): void {
    if (this.saving()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.error.set('Complétez les champs obligatoires (marqués *).');
      return;
    }

    this.saving.set(true);
    this.error.set('');
    this.success.set('');

    // Création : champs vides omis. Modification : un champ vidé est envoyé vide (null
    // pour les listes, dates et montants) pour être effacé côté serveur.
    const raw = this.form.value;   // sans les champs verrouillés (immatriculation, compteur)
    const NULLABLES = ['numero_chassis', 'affectation', 'chauffeur_attitré', 'statut', 'date_mise_en_service',
                       'date_acquisition', 'valeur_acquisition', 'marque', 'modele'];
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([key, val]) => {
      const vide = val === '' || val === null || val === undefined;
      if (vide) {
        if (this.isEditMode()) payload[key] = NULLABLES.includes(key) ? null : (typeof val === 'string' ? '' : val);
        return;
      }
      // valeur_acquisition en texte : pas de perte de précision sur les grands nombres
      payload[key] = key === 'valeur_acquisition' && typeof val === 'number' ? String(Math.round(val)) : val;
    });
    Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

    const request = this.isEditMode()
      ? this.vehiculeApi.update(this.id()!, payload)
      : this.vehiculeApi.create(payload);

    request.subscribe({
      next: (v) => {
        this.saving.set(false);
        this.success.set(this.isEditMode()
          ? 'Véhicule modifié avec succès.'
          : 'Véhicule créé avec succès.');
        setTimeout(() => this.router.navigate(['/vehicules', v.id]), 1200);
      },
      error: (err) => {
        this.saving.set(false);
        if (err?.error && typeof err.error === 'object') {
          this.error.set(messageErreurApi(err, 'Enregistrement impossible.'));
        } else if (err?.status === 0) {
          this.error.set('Serveur inaccessible. Vérifiez que le backend est démarré.');
        } else {
          this.error.set('Une erreur est survenue. Veuillez réessayer.');
        }
      },
    });
  }

  cancel(): void {
    if (this.isEditMode()) {
      this.router.navigate(['/vehicules', this.id()]);
    } else {
      this.router.navigate(['/vehicules']);
    }
  }
}
