// UbiFleet — Vehicule Form Component (Angular 18 — Ajout & Modification)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { VehiculeApiService, AgenceApiService, ChauffeurApiService, ParametrageApiService } from '../../../core/services/api.service';
import { Agence, Chauffeur } from '../../../core/models';

@Component({
  selector: 'ubi-vehicule-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
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
  private chauffeurApi = inject(ChauffeurApiService);

  isEditMode = computed(() => !!this.id());

  agences    = signal<Agence[]>([]);
  chauffeurs = signal<Chauffeur[]>([]);
  loading    = signal(false);
  saving     = signal(false);
  error      = signal('');
  success    = signal('');

  // Options statiques
  readonly typesVehicule = [
    { value: 'berline',     label: 'Berline' },
    { value: 'suv',         label: 'SUV / 4×4' },
    { value: 'minibus',     label: 'Minibus' },
    { value: 'camionnette', label: 'Camionnette' },
    { value: 'pickup',      label: 'Pick-up' },
    { value: 'camion',      label: 'Camion' },
    { value: 'moto',        label: 'Moto' },
  ];

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
      next: (l) => this.statutsVehicule.set(l.filter((s: any) => s.actif)),
      error: () => {},
    });
    this.parametrageApi.getAffectations().subscribe({
      next: (l) => this.affectationsUsage.set(l.filter((a: any) => a.actif)),
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

    this.chauffeurApi.getAll({ page_size: 100 }).subscribe({
      next: (res) => this.chauffeurs.set(res.results),
      error: () => {},
    });

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
    if (this.form.invalid || this.saving()) return;

    this.saving.set(true);
    this.error.set('');
    this.success.set('');

    // Nettoyer les valeurs vides
    const raw = this.form.value;
    const payload: Record<string, any> = {};
    Object.entries(raw).forEach(([key, val]) => {
      if (val !== '' && val !== null && val !== undefined) {
        // valeur_acquisition : envoyer en string pour éviter
        // la perte de précision float des grands nombres (ex: 20000000)
        if (key === 'valeur_acquisition' && typeof val === 'number') {
          payload[key] = String(Math.round(val));
        } else {
          payload[key] = val;
        }
      }
    });

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
        if (err?.error) {
          // Afficher les erreurs de validation du backend
          const msgs = Object.entries(err.error)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ');
          this.error.set(msgs);
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
