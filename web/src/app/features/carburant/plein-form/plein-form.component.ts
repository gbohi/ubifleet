// UbiFleet — Plein Form Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, computed, effect
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AbstractControl, FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { CarburantApiService, AgenceApiService, VehiculeApiService, ChauffeurApiService, ParametrageApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';
import { FenetreSaisieService, messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { HistoriqueCorrectionsComponent } from '../../../shared/corrections/historique-corrections.component';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';

@Component({
  selector: 'ubi-plein-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, DecimalPipe, DatePipe, HistoriqueCorrectionsComponent, SuppressionMotifComponent],
  templateUrl: './plein-form.component.html',
  styleUrls: ['./plein-form.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PleinFormComponent implements OnInit {
  id = input<string | undefined>(undefined);

  private fb           = inject(FormBuilder);
  private router       = inject(Router);
  private carburantApi = inject(CarburantApiService);
  private agenceApi    = inject(AgenceApiService);
  private vehiculeApi  = inject(VehiculeApiService);
  private chauffeurApi   = inject(ChauffeurApiService);
  private parametrageApi = inject(ParametrageApiService);
  readonly fenetres      = inject(FenetreSaisieService);

  isEditMode = computed(() => !!this.id());
  agences    = signal<Agence[]>([]);
  vehicules  = signal<{ id: string; immatriculation: string; designation: string; agenceId: string }[]>([]);
  chauffeurs = signal<{ id: string; nom_complet: string }[]>([]);
  tournees   = signal<any[]>([]);
  stations   = signal<any[]>([]);
  /** Prix en vigueur à la date du plein pour le carburant du véhicule. */
  prixReference = signal<{ prix: number | null; date_effet: string | null; type_carburant: string } | null>(null);
  private dernierPrixAuto: number | null = null;
  loading    = signal(false);
  saving     = signal(false);
  error      = signal('');
  success    = signal('');
  /** Plein sorti de la fenêtre de saisie : consultation seule. */
  verrouille = signal(false);
  /** Pas de droit de modification (ni rôle autorisé, ni auteur dans la fenêtre). */
  lectureSeule = signal(false);
  supprimable  = signal(false);
  /** Date d'origine hors de la fenêtre : toute correction exige un motif. */
  horsFenetre  = signal(false);
  infoHorsDelai = signal<string | null>(null);
  motifCorrection = signal('');
  private dateCourante = signal<string | null>(null);
  motifRequis = computed(() => this.isEditMode()
    && (this.horsFenetre() || this.fenetres.horsDelai('carburant', this.dateCourante())));
  suppression        = signal(false);
  suppressionEnCours = signal(false);
  suppressionErreur  = signal('');

  // ── Photo tableau de bord ──
  photoFile        = signal<File | null>(null);
  photoPreview     = signal<string | null>(null);   // data URL pour prévisualisation
  photoExistante   = signal<string | null>(null);   // URL de la photo déjà enregistrée
  photoSupprimee   = signal(false);                 // si l'utilisateur veut supprimer la photo

  form = this.fb.group({
    vehicule:           ['', Validators.required],
    chauffeur:          [null as string | null],
    tournee:            [null as number | null],
    station:            [null as string | null],
    date_plein:         [new Date().toISOString().split('T')[0],
                         [Validators.required, (c: AbstractControl) => this.fenetres.erreur('carburant', c.value) ? { fenetre: true } : null]],
    heure_plein:        [this.currentTimeStr(), Validators.required],
    volume_litres:      [null as number | null, [Validators.required, Validators.min(0.1)]],
    prix_litre:         [null as number | null],
    bon_carburant:      [''],
    kilometrage_releve: [null as number | null, Validators.required],
    agence:             ['', Validators.required],
    notes:              [''],
  });

  get f() { return this.form.controls; }

  /** Plein enregistré sans heure (avant qu'elle soit obligatoire) : à compléter. */
  heureManquante = signal(false);

  private currentTimeStr(): string {
    const now = new Date();
    return `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  }

  get montantCalcule(): number {
    const vol  = Number(this.form.value.volume_litres  ?? 0);
    const prix = Number(this.form.value.prix_litre ?? 0);
    return vol > 0 && prix > 0 ? parseFloat((vol * prix).toFixed(2)) : 0;
  }

  constructor() {
    // Bornes reçues du serveur : date et heure du serveur par défaut, puis revalidation
    effect(() => {
      const f = this.fenetres.fenetre('carburant');
      if (!f) return;
      const date = this.form.controls.date_plein;
      const heure = this.form.controls.heure_plein;
      if (!this.isEditMode() && !date.dirty) date.setValue(f.date_max);
      if (!this.isEditMode() && !heure.dirty) heure.setValue(this.fenetres.heureServeur() ?? heure.value);
      date.updateValueAndValidity();
    });
  }

  dateErreur(): string | null {
    return this.fenetres.erreur('carburant', this.form.controls.date_plein.value);
  }

  ngOnInit(): void {
    this.fenetres.charger();
    this.dateCourante.set(this.form.controls.date_plein.value);
    this.form.controls.date_plein.valueChanges.subscribe(d => this.dateCourante.set(d));
    this.parametrageApi.getTournees().subscribe({
      next: (l) => this.tournees.set(l.filter((t: any) => t.actif)),
      error: () => {},
    });
    // Stations actives (de l'agence de l'utilisateur et stations communes)
    this.carburantApi.getStations({ page_size: 500 }).subscribe({
      next: (res: any) => this.stations.set(Array.isArray(res) ? res : (res.results ?? [])),
      error: () => {},
    });
    // Prix au litre : prix en vigueur à la date du plein, recalculé quand le
    // véhicule ou la date change (sauf si l'utilisateur a saisi un autre prix)
    this.form.controls.date_plein.valueChanges.subscribe(() => this.chargerPrix());
    this.agenceApi.getAll().subscribe({
      next: (list) => this.agences.set(Array.isArray(list) ? list : []),
      error: () => {},
    });

    this.vehiculeApi.getAll({ page_size: 200 }).subscribe({
      next: (res) => {
        const list = Array.isArray(res) ? res : (res.results ?? []);
        this.vehicules.set(list.map(v => ({
          id: v.id, immatriculation: v.immatriculation,
          designation: v.designation, agenceId: v.agence,
        })));
      },
      error: () => {},
    });

    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res) => this.chauffeurs.set(
        res.results.map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });

    if (this.isEditMode() && this.id()) {
      this.loading.set(true);
      this.carburantApi.getPlein(this.id()!).subscribe({
        next: (p: any) => {
          if (p) {
            this.form.patchValue({
              vehicule:           p.vehicule,
              chauffeur:          p.chauffeur,
              tournee:            p.tournee ?? null,
              station:            p.station ?? null,
              date_plein:         p.date_plein,
              heure_plein:        p.heure_plein ? p.heure_plein.substring(0, 5) : null,
              volume_litres:      p.volume_litres,
              prix_litre:         p.prix_litre,
              bon_carburant:      p.bon_carburant,
              kilometrage_releve: p.kilometrage_releve,
              agence:             p.agence,
              notes:              p.notes ?? '',
            });
            this.heureManquante.set(!p.heure_plein);
            if (p.photo_tableau_bord) {
              this.photoExistante.set(p.photo_tableau_bord);
            }
            this.verrouille.set(!!p.verrouille);
            this.lectureSeule.set(!!p.verrouille || p.modifiable === false);
            this.supprimable.set(!!p.supprimable);
            this.horsFenetre.set(!!p.hors_fenetre);
            if (this.lectureSeule()) this.form.disable();
            if (p.saisie_hors_delai) {
              this.infoHorsDelai.set(`Saisi ou corrigé hors délai${p.hors_delai_par_nom ? ' par ' + p.hors_delai_par_nom : ''}`
                + (p.hors_delai_le ? ` le ${new Date(p.hors_delai_le).toLocaleDateString('fr-FR')}` : '') + '.');
            }
          }
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
    }
  }

  onVehiculeChange(event: Event): void {
    const id = (event.target as HTMLSelectElement).value;
    const v  = this.vehicules().find(x => x.id === id);
    if (v && v.agenceId) this.form.patchValue({ agence: v.agenceId });
    this.chargerPrix(id);
  }

  /** `vehiculeId` : valeur venant de l'événement (le contrôle peut ne pas être encore à jour). */
  chargerPrix(vehiculeId?: string): void {
    const vehicule = vehiculeId ?? this.form.value.vehicule;
    const date = this.form.value.date_plein;
    if (!vehicule || !date) { this.prixReference.set(null); return; }
    this.carburantApi.prixEnVigueur({ vehicule, date }).subscribe({
      next: (r: any) => {
        const prix = r.prix !== null ? Number(r.prix) : null;
        this.prixReference.set({ prix, date_effet: r.date_effet, type_carburant: r.type_carburant });
        const actuel = this.form.value.prix_litre;
        // Ne pas écraser un prix saisi à la main
        if (prix !== null && (actuel === null || actuel === undefined || Number(actuel) === this.dernierPrixAuto)) {
          this.form.patchValue({ prix_litre: prix });
          this.dernierPrixAuto = prix;
        }
      },
      error: () => this.prixReference.set(null),
    });
  }

  // ── Gestion photo tableau de bord ──
  onPhotoChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file  = input.files?.[0];
    if (!file) return;

    // Vérifier type et taille (max 5 Mo)
    if (!file.type.startsWith('image/')) {
      this.error.set('Le fichier doit être une image (JPG, PNG, WebP...).');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.error.set('La photo ne doit pas dépasser 5 Mo.');
      return;
    }
    this.error.set('');
    this.photoFile.set(file);
    this.photoSupprimee.set(false);

    // Générer la prévisualisation
    const reader = new FileReader();
    reader.onload = (e) => this.photoPreview.set(e.target?.result as string);
    reader.readAsDataURL(file);
  }

  clearPhoto(): void {
    this.photoFile.set(null);
    this.photoPreview.set(null);
    if (this.photoExistante()) this.photoSupprimee.set(true);
  }

  currentPhotoUrl(): string | null {
    if (this.photoPreview()) return this.photoPreview();
    if (!this.photoSupprimee() && this.photoExistante()) return this.photoExistante();
    return null;
  }

  // ── Submit ──
  onSubmit(): void {
    if (this.form.invalid || this.saving() || this.lectureSeule()) return;
    if (this.motifRequis() && !this.motifCorrection().trim()) return;
    this.saving.set(true);
    this.error.set('');
    this.success.set('');

    const raw = this.form.value;

    // Toujours utiliser FormData pour supporter les fichiers
    const fd = new FormData();

    Object.entries(raw).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) fd.append(k, String(v));
    });

    // Calculer montant_fcfa si absent
    const vol  = Number(raw.volume_litres ?? 0);
    const prix = Number(raw.prix_litre    ?? 0);
    fd.append('montant_fcfa', prix > 0 ? (vol * prix).toFixed(2) : '0.00');

    if (this.isEditMode() && this.motifCorrection().trim()) {
      fd.append('motif_correction', this.motifCorrection().trim());
    }

    // Photo tableau de bord
    if (this.photoFile()) {
      fd.append('photo_tableau_bord', this.photoFile()!);
    } else if (this.photoSupprimee()) {
      fd.append('photo_tableau_bord', '');   // vider le champ
    }

    const req = this.isEditMode()
      ? this.carburantApi.updatePlein(this.id()!, fd)
      : this.carburantApi.createPlein(fd);

    req.subscribe({
      next: () => {
        this.saving.set(false);
        this.success.set(this.isEditMode() ? 'Plein modifié.' : 'Plein enregistré.');
        setTimeout(() => this.router.navigate(['/carburant']), 1200);
      },
      error: (err) => {
        this.saving.set(false);
        this.error.set(messageErreurApi(err, 'Une erreur est survenue.'));
      },
    });
  }

  supprimer(motif: string): void {
    if (!this.id() || this.suppressionEnCours()) return;
    this.suppressionEnCours.set(true);
    this.suppressionErreur.set('');
    this.carburantApi.deletePlein(this.id()!, motif || undefined).subscribe({
      next: () => {
        this.suppressionEnCours.set(false);
        this.suppression.set(false);
        this.router.navigate(['/carburant']);
      },
      error: (err) => {
        this.suppressionEnCours.set(false);
        this.suppressionErreur.set(messageErreurApi(err, 'Suppression impossible.'));
      },
    });
  }

  cancel(): void { this.router.navigate(['/carburant']); }
}
