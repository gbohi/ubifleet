// UbiFleet — Historique Kilométrage (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, effect, computed
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AbstractControl, FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { VehiculeApiService, ChauffeurApiService } from '../../../core/services/api.service';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { FenetreSaisieService, heureLocale, messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { HistoriqueCorrectionsComponent } from '../../../shared/corrections/historique-corrections.component';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';
import { ReleveKilometrage, TypeMouvement } from '../../../core/models';

@Component({
  selector: 'ubi-vehicule-releves-km',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule, HistoriqueCorrectionsComponent, SuppressionMotifComponent],
  templateUrl: './vehicule-releves-km.component.html',
  styleUrls: ['./vehicule-releves-km.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculeRelevesKmComponent implements OnInit {
  id = input.required<string>();

  private router     = inject(Router);
  private route      = inject(ActivatedRoute);
  private fb         = inject(FormBuilder);
  private vehiculeApi  = inject(VehiculeApiService);
  private chauffeurApi = inject(ChauffeurApiService);

  releves     = signal<ReleveKilometrage[]>([]);
  total       = signal(0);
  page        = signal(1);
  loading     = signal(true);
  showForm    = signal(false);
  editId      = signal<string | null>(null);
  saving      = signal(false);
  error       = signal('');
  success     = signal('');
  /** Relevé en cours de modification (null = création). */
  releveEdite = signal<ReleveKilometrage | null>(null);
  motifCorrection = signal('');
  private dateCourante = signal<string | null>(null);
  /** Motif obligatoire : relevé sorti de la fenêtre, ou nouvelle date hors fenêtre. */
  motifRequis = computed(() => !!this.releveEdite()
    && (!!this.releveEdite()!.hors_fenetre || this.fenetres.horsDelai('releves', this.dateCourante())));
  /** Relevé ancien enregistré sans heure : on ne force pas à en inventer une. */
  heureFacultative = computed(() => !!this.releveEdite() && !this.releveEdite()!.heure_releve);
  releveASupprimer = signal<ReleveKilometrage | null>(null);
  deleteEnCours    = signal(false);
  deleteErreur     = signal('');
  historiqueDe     = signal<ReleveKilometrage | null>(null);
  vehiculeInfo = signal<{ immatriculation: string; designation: string; km: number } | null>(null);

  chauffeurs  = signal<{ id: string; nom_complet: string }[]>([]);
  photoFile   = signal<File | null>(null);
  photoPreview = signal<string | null>(null);
  photoLightbox = signal<string | null>(null);

  // Types de mouvement paramétrables (Paramètres › Types de mouvement)
  typesMvt = inject(TypesMouvementService);
  readonly fenetres = inject(FenetreSaisieService);

  form = this.fb.group({
    kilometrage:    [null as number | null, [Validators.required, Validators.min(0)]],
    date_releve:    [new Date().toISOString().split('T')[0],
                     [Validators.required, (c: AbstractControl) => this.fenetres.erreur('releves', c.value) ? { fenetre: true } : null]],
    heure_releve:   [null as string | null,
                     (c: AbstractControl) => !c.value && !this.heureFacultative() ? { required: true } : null],
    type_mouvement: ['releve', Validators.required],
    tournee:        [''],
    chauffeur:      [''],
    notes:          [''],
  });

  constructor() {
    // Revalider la date à la réception des bornes du serveur
    effect(() => {
      if (!this.fenetres.fenetre('releves')) return;
      this.f['date_releve'].updateValueAndValidity();
      // Nouveau relevé : heure du serveur, tant que l'utilisateur ne l'a pas changée
      const heure = this.f['heure_releve'];
      if (!this.editId() && !heure.dirty) heure.setValue(this.fenetres.heureServeur() ?? heure.value);
    });
  }

  get f() { return this.form.controls; }

  dateErreur(): string | null { return this.fenetres.erreur('releves', this.f['date_releve'].value); }

  get totalPages(): number { return Math.ceil(this.total() / 20) || 1; }
  get pages(): number[] {
    const cur = this.page();
    const max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.typesMvt.charger();
    this.f['date_releve'].valueChanges.subscribe(d => this.dateCourante.set(d));
    this.loadReleves(this.route.snapshot.queryParamMap.get('modifier'));
    // Charger les infos du véhicule
    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res) => this.chauffeurs.set(
        (res.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });
    this.vehiculeApi.getById(this.id()).subscribe({
      next: (v: any) => this.vehiculeInfo.set({
        immatriculation: v.immatriculation,
        designation:     v.designation,
        km:              v.kilometrage_actuel,
      }),
      error: () => {},
    });
  }

  /** `aModifier` : relevé à ouvrir en modification (lien « Corriger » de la liste globale). */
  loadReleves(aModifier?: string | null): void {
    this.loading.set(true);
    this.vehiculeApi.getRelevesKm({ vehicule: this.id(), page: this.page() }).subscribe({
      next: (res) => {
        this.releves.set(res.results ?? []);
        this.total.set(res.count ?? 0);
        this.loading.set(false);
        if (aModifier) {
          const r = this.releves().find(x => x.id === aModifier);
          if (r?.modifiable) this.openForm(r);
          else if (r) this.historiqueDe.set(r);
        }
      },
      error: () => this.loading.set(false),
    });
  }

  openForm(releve?: ReleveKilometrage): void {
    this.error.set('');
    this.success.set('');
    this.motifCorrection.set('');
    this.releveEdite.set(releve ?? null);
    if (releve) {
      this.editId.set(releve.id);
      this.form.patchValue({
        kilometrage:    releve.kilometrage,
        date_releve:    releve.date_releve,
        heure_releve:   releve.heure_releve ? releve.heure_releve.substring(0, 5) : null,
        type_mouvement: releve.type_mouvement,
        chauffeur:      releve.chauffeur ?? '',
        tournee:        releve.tournee ?? '',
        notes:          releve.notes,
      });
    } else {
      this.editId.set(null);
      this.form.reset({
        date_releve: this.fenetres.max('releves') ?? new Date().toISOString().split('T')[0],
        heure_releve: this.fenetres.heureServeur() ?? heureLocale(),
        type_mouvement: 'releve',
      });
    }
    this.fenetres.charger();
    this.showForm.set(true);
  }

  closeForm(): void {
    this.showForm.set(false);
    this.photoFile.set(null);
    this.photoPreview.set(null);
  }

  onPhotoChange(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.photoFile.set(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => this.photoPreview.set(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      this.photoPreview.set(null);
    }
  }

  openLightbox(url: string): void  { this.photoLightbox.set(url); }
  closeLightbox(): void             { this.photoLightbox.set(null); }

  saveReleve(): void {
    if (this.form.invalid || this.saving()) return;
    if (this.motifRequis() && !this.motifCorrection().trim()) return;
    this.saving.set(true);
    this.error.set('');

    const raw = this.form.value;
    const payload: Record<string, any> = {
      vehicule:       this.id(),
      kilometrage:    raw.kilometrage,
      date_releve:    raw.date_releve,
      type_mouvement: raw.type_mouvement,
    };
    if (raw.heure_releve) payload['heure_releve'] = raw.heure_releve;
    const edition = this.editId();
    if (edition) {
      // Modification : champs vidés transmis, motif conservé dans le journal
      payload['chauffeur'] = raw.chauffeur || null;
      payload['tournee']   = raw.tournee || '';
      payload['notes']     = raw.notes || '';
      if (this.motifCorrection().trim()) payload['motif_correction'] = this.motifCorrection().trim();
    } else {
      if (raw.chauffeur) payload['chauffeur'] = raw.chauffeur;
      if (raw.tournee)   payload['tournee']   = raw.tournee;
      if (raw.notes)     payload['notes']     = raw.notes;
    }
    if (this.photoFile()) payload['photo_tableau_bord'] = this.photoFile()!

    const req = edition
      ? this.vehiculeApi.updateReleveKm(edition, payload)
      : this.vehiculeApi.createReleveKm(payload as any);
    req.subscribe({
      next: () => {
        this.saving.set(false);
        this.success.set(edition ? 'Relevé corrigé.' : 'Relevé enregistré.');
        this.closeForm();
        this.loadReleves();
        this.rafraichirVehicule();   // km actuel recalculé par le serveur
      },
      error: (err) => {
        this.saving.set(false);
        this.error.set(messageErreurApi(err, 'Erreur lors de l\'enregistrement.'));
      },
    });
  }

  confirmDelete(r: ReleveKilometrage): void {
    this.deleteErreur.set('');
    this.releveASupprimer.set(r);
  }

  doDelete(motif: string): void {
    const r = this.releveASupprimer();
    if (!r || this.deleteEnCours()) return;
    this.deleteEnCours.set(true);
    this.vehiculeApi.deleteReleveKm(r.id, motif || undefined).subscribe({
      next: () => {
        this.deleteEnCours.set(false);
        this.releveASupprimer.set(null);
        this.success.set('Relevé supprimé.');
        this.loadReleves();
        this.rafraichirVehicule();
      },
      error: (err) => {
        this.deleteEnCours.set(false);
        this.deleteErreur.set(messageErreurApi(err, 'Suppression impossible.'));
      },
    });
  }

  /** Kilométrage actuel du véhicule (recalculé par le serveur après une correction). */
  rafraichirVehicule(): void {
    this.vehiculeApi.getById(this.id()).subscribe({
      next: (v: any) => this.vehiculeInfo.set({
        immatriculation: v.immatriculation, designation: v.designation, km: v.kilometrage_actuel,
      }),
      error: () => {},
    });
  }

  onPageChange(p: number): void { this.page.set(p); this.loadReleves(); }
  goBack(): void { this.router.navigate(['/vehicules', this.id()]); }

  typeMouvementClass(type: TypeMouvement): string {
    return this.typesMvt.classeBadge(type);
  }

  typeMouvementIcon(type: TypeMouvement): string {
    const map: Record<string, string> = {
      entree: 'fa-sign-in-alt', sortie: 'fa-sign-out-alt',
      releve: 'fa-tachometer-alt', tournee: 'fa-route',
    };
    return map[type] ?? 'fa-circle';
  }
}
