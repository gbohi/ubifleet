// UbiFleet — Contrôle Véhicule (Angular 18)
import {
  Component, inject, OnInit, ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  ControleApiService, AgenceApiService, ChauffeurApiService, VehiculeApiService
} from '../../core/services/api.service';

type Tab = 'fiches' | 'elements' | 'nouvelle';

interface Element {
  id: number; nom: string; categorie: string;
  categorie_display: string; ordre: number; actif: boolean; obligatoire: boolean;
}
interface Fiche {
  id: string; vehicule_immat: string; chauffeur_nom: string | null;
  agence_nom: string; type_controle: string; type_controle_display: string;
  statut_global: string; statut_global_display: string;
  date_heure: string; kilometrage: number;
  nb_points: number; nb_non_conformes: number; nb_photos: number;
}
interface PointState { statut: string; gravite: string; remarque: string; }

const CATEGORIES = [
  { value: 'moteur',         label: 'Moteur' },
  { value: 'securite',       label: 'Sécurité' },
  { value: 'carrosserie',    label: 'Carrosserie' },
  { value: 'eclairage',      label: 'Éclairage' },
  { value: 'pneumatiques',   label: 'Pneumatiques' },
  { value: 'interieur',      label: 'Intérieur' },
  { value: 'administratif',  label: 'Administratif' },
  { value: 'autre',          label: 'Autre' },
];

@Component({
  selector: 'ubi-controle',
  standalone: true,
  imports: [RouterLink, DatePipe, ReactiveFormsModule],
  templateUrl: './controle.component.html',
  styleUrls:   ['./controle.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ControleComponent implements OnInit {
  private api          = inject(ControleApiService);
  private agenceApi    = inject(AgenceApiService);
  private chauffeurApi = inject(ChauffeurApiService);
  private vehiculeApi  = inject(VehiculeApiService);
  private router       = inject(Router);
  private fb           = inject(FormBuilder);

  activeTab   = signal<Tab>('fiches');
  categories  = CATEGORIES;

  // ── Fiches ──────────────────────────────────────────────────────
  fiches        = signal<Fiche[]>([]);
  fichesTotal   = signal(0);
  fichesLoading = signal(false);
  stats         = signal<any>(null);

  filtreImmat  = signal('');
  filtreType   = signal('');
  filtreStatut = signal('');
  filtreDebut  = signal('');
  filtreFin    = signal('');
  filtrePage   = signal(1);
  readonly pageSize = 20;

  // ── Nouvelle fiche ───────────────────────────────────────────────
  agences      = signal<any[]>([]);
  chauffeurs   = signal<any[]>([]);
  vehicules    = signal<any[]>([]);  // liste pour recherche
  vehiculeSearch = signal('');
  elements     = signal<Element[]>([]);
  pointsMap    = signal<Record<number, PointState>>({});
  photosGlobales  = signal<File[]>([]);
  photosPreviews  = signal<string[]>([]);
  ficheLoading = signal(false);
  ficheError   = signal('');
  ficheSuccess = signal('');

  ficheForm = this.fb.group({
    vehicule:        ['', Validators.required],
    chauffeur:       [''],
    agence:          [''],
    type_controle:   ['periodique', Validators.required],
    date_heure:      [new Date().toISOString().slice(0, 16), Validators.required],
    kilometrage:     [0, [Validators.required, Validators.min(0)]],
    notes_generales: [''],
  });

  // ── Éléments ─────────────────────────────────────────────────────
  eleLoading = signal(false);
  eleError   = signal('');
  eleSuccess = signal('');
  editEleId  = signal<number | null>(null);
  eleForm    = this.fb.group({
    nom:         ['', Validators.required],
    categorie:   ['autre', Validators.required],
    ordre:       [0],
    obligatoire: [false],
    actif:       [true],
  });

  get categoriesGrouped(): Record<string, Element[]> {
    const g: Record<string, Element[]> = {};
    for (const cat of this.categories) g[cat.value] = [];
    for (const e of this.elements()) {
      if (g[e.categorie]) g[e.categorie].push(e);
    }
    return g;
  }

  get pointCount(): number {
    return Object.values(this.pointsMap()).length;
  }

  get pointsNonConformes(): number {
    return Object.values(this.pointsMap()).filter(p => p.statut === 'non_conforme').length;
  }

  ngOnInit(): void {
    this.loadFiches();
    this.loadElements();
    this.loadStats();
    this.agenceApi.getAll().subscribe({
      next: (r: any) => this.agences.set(r.results ?? r ?? []),
      error: () => {},
    });
    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (r: any) => this.chauffeurs.set(
        (r.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });
    // Charger les véhicules pour la sélection
    this.vehiculeApi.getAll({ page_size: 200, statut: 'en_service' }).subscribe({
      next: (r: any) => this.vehicules.set(r.results ?? r ?? []),
      error: () => {},
    });
  }

  loadFiches(): void {
    this.fichesLoading.set(true);
    const params: Record<string, any> = {
      page: this.filtrePage(), page_size: this.pageSize
    };
    if (this.filtreImmat())  params['immatriculation'] = this.filtreImmat();
    if (this.filtreType())   params['type_controle']   = this.filtreType();
    if (this.filtreStatut()) params['statut_global']   = this.filtreStatut();
    if (this.filtreDebut())  params['date_debut']      = this.filtreDebut();
    if (this.filtreFin())    params['date_fin']        = this.filtreFin();
    this.api.getFiches(params).subscribe({
      next: (r: any) => {
        this.fiches.set(r.results ?? r ?? []);
        this.fichesTotal.set(r.count ?? 0);
        this.fichesLoading.set(false);
      },
      error: () => this.fichesLoading.set(false),
    });
  }

  loadElements(): void {
    this.eleLoading.set(true);
    this.api.getElements().subscribe({
      next: (list) => { this.elements.set(list); this.eleLoading.set(false); },
      error: () => this.eleLoading.set(false),
    });
  }

  loadStats(): void {
    this.api.getStatsFiches().subscribe({
      next: (s) => this.stats.set(s), error: () => {}
    });
  }

  onFiltreInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement | HTMLSelectElement).value;
    if (field === 'immat')  this.filtreImmat.set(val);
    if (field === 'type')   this.filtreType.set(val);
    if (field === 'statut') this.filtreStatut.set(val);
    if (field === 'debut')  this.filtreDebut.set(val);
    if (field === 'fin')    this.filtreFin.set(val);
    this.filtrePage.set(1);
    this.loadFiches();
  }

  // ── Nouvelle fiche ────────────────────────────────────────────────
  onTabChange(t: Tab): void {
    this.activeTab.set(t);
    if (t === 'nouvelle' && Object.keys(this.pointsMap()).length === 0) {
      this.initPointsMap();
    }
  }

  initPointsMap(): void {
    const map: Record<number, PointState> = {};
    for (const e of this.elements()) {
      if (e.actif) map[e.id] = { statut: 'conforme', gravite: '', remarque: '' };
    }
    this.pointsMap.set(map);
  }

  setPoint(id: number, field: keyof PointState, val: string): void {
    const m = { ...this.pointsMap() };
    m[id] = { ...m[id], [field]: val };
    if (field === 'statut' && val !== 'non_conforme') m[id].gravite = '';
    this.pointsMap.set(m);
  }

  // Recherche véhicule
  onVehiculeSearch(e: Event): void {
    this.vehiculeSearch.set((e.target as HTMLInputElement).value);
  }

  get vehiculesFiltres(): any[] {
    const q = this.vehiculeSearch().toLowerCase();
    if (!q) return this.vehicules().slice(0, 10);
    return this.vehicules()
      .filter(v => v.immatriculation?.toLowerCase().includes(q) ||
                   (v.marque_libelle ?? '').toLowerCase().includes(q))
      .slice(0, 10);
  }

  selectVehicule(v: any): void {
    this.ficheForm.patchValue({ vehicule: v.id });
    this.vehiculeSearch.set(v.immatriculation + ' — ' + (v.marque_libelle ?? '') + ' ' + (v.modele_libelle ?? ''));
  }

  // Photos globales
  onPhotosGlobalesChange(e: Event): void {
    const files = Array.from((e.target as HTMLInputElement).files ?? []);
    this.photosGlobales.set(files);
    const previews = files.map(f => URL.createObjectURL(f));
    this.photosPreviews.set(previews);
  }

  removePhoto(i: number): void {
    const files = [...this.photosGlobales()];
    files.splice(i, 1);
    this.photosGlobales.set(files);
    const prev = [...this.photosPreviews()];
    URL.revokeObjectURL(prev[i]);
    prev.splice(i, 1);
    this.photosPreviews.set(prev);
  }

  creerFicheEtSauvegarder(): void {
    if (this.ficheForm.invalid) return;
    this.ficheLoading.set(true);
    this.ficheError.set('');

    const raw = this.ficheForm.value as any;
    const payload: any = {
      vehicule:        raw.vehicule,
      type_controle:   raw.type_controle,
      date_heure:      raw.date_heure,
      kilometrage:     raw.kilometrage,
      notes_generales: raw.notes_generales || '',
    };
    if (raw.chauffeur) payload.chauffeur = raw.chauffeur;
    if (raw.agence)    payload.agence    = raw.agence;

    this.api.createFiche(payload).subscribe({
      next: (fiche: any) => {
        // Sauvegarder les points
        const points = Object.entries(this.pointsMap()).map(([id, v]) => ({
          element: Number(id),
          statut:  v.statut,
          gravite: v.gravite || null,
          remarque: v.remarque,
        }));

        this.api.bulkSavePoints(fiche.id, points).subscribe({
          next: () => {
            // Uploader les photos globales
            const photos = this.photosGlobales();
            if (photos.length === 0) {
              this.finishCreation(fiche.id);
              return;
            }
            let uploaded = 0;
            for (const photo of photos) {
              const fd = new FormData();
              fd.append('fiche', fiche.id);
              fd.append('image', photo);
              fd.append('type_photo', 'autre');
              this.api.uploadPhoto(fiche.id, fd).subscribe({
                next: () => { uploaded++; if (uploaded === photos.length) this.finishCreation(fiche.id); },
                error: () => { uploaded++; if (uploaded === photos.length) this.finishCreation(fiche.id); },
              });
            }
          },
          error: () => {
            this.ficheLoading.set(false);
            this.ficheError.set('Fiche créée mais erreur lors de la sauvegarde des points.');
          },
        });
      },
      error: (err: any) => {
        this.ficheLoading.set(false);
        this.ficheError.set(err?.error?.detail ?? 'Erreur lors de la création de la fiche.');
      },
    });
  }

  private finishCreation(ficheId: string): void {
    this.ficheLoading.set(false);
    this.ficheSuccess.set('Fiche créée avec succès.');
    this.ficheForm.reset({ type_controle: 'periodique', kilometrage: 0, date_heure: new Date().toISOString().slice(0,16) });
    this.pointsMap.set({});
    this.photosGlobales.set([]);
    this.photosPreviews.set([]);
    this.vehiculeSearch.set('');
    this.loadFiches();
    this.loadStats();
    setTimeout(() => {
      this.ficheSuccess.set('');
      this.activeTab.set('fiches');
    }, 1500);
  }

  voirRapport(id: string): void {
    this.router.navigate(['/controle', id]);
  }

  validerFiche(id: string): void {
    this.api.validerFiche(id).subscribe({
      next: () => {
        this.loadFiches();
        this.loadStats();
      },
      error: () => {},
    });
  }

  // ── Éléments CRUD ────────────────────────────────────────────────
  editElement(e: Element): void {
    this.editEleId.set(e.id);
    this.eleForm.patchValue({
      nom: e.nom, categorie: e.categorie,
      ordre: e.ordre, obligatoire: e.obligatoire, actif: e.actif
    });
  }

  cancelEditElement(): void {
    this.editEleId.set(null);
    this.eleForm.reset({ categorie: 'autre', ordre: 0, obligatoire: false, actif: true });
  }

  saveElement(): void {
    if (this.eleForm.invalid) return;
    const id  = this.editEleId();
    const req = id
      ? this.api.updateElement(id, this.eleForm.value)
      : this.api.createElement(this.eleForm.value);
    req.subscribe({
      next: () => {
        this.eleSuccess.set(id ? 'Élément modifié.' : 'Élément créé.');
        this.cancelEditElement();
        this.loadElements();
        setTimeout(() => this.eleSuccess.set(''), 3000);
      },
      error: (err: any) => this.eleError.set(err?.error?.detail ?? 'Erreur.'),
    });
  }

  toggleActifElement(e: Element): void {
    this.api.updateElement(e.id, { actif: !e.actif }).subscribe({
      next: () => this.loadElements(), error: () => {}
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────
  statutClass(s: string): string {
    const m: Record<string, string> = {
      conforme: 'badge-green', non_conforme: 'badge-danger',
      partiel: 'badge-warning', en_cours: 'badge-gray'
    };
    return m[s] ?? 'badge-gray';
  }

  typeIcon(t: string): string {
    const m: Record<string, string> = {
      depart: 'fas fa-sign-out-alt', retour: 'fas fa-sign-in-alt',
      periodique: 'fas fa-calendar-check', apres_sinistre: 'fas fa-car-crash',
      apres_reparation: 'fas fa-tools'
    };
    return m[t] ?? 'fas fa-clipboard-check';
  }

  get totalPages(): number { return Math.ceil(this.fichesTotal() / this.pageSize) || 1; }
  get pages(): number[] {
    const t = this.totalPages, c = this.filtrePage(), r: number[] = [];
    for (let i = Math.max(1, c - 2); i <= Math.min(t, c + 2); i++) r.push(i);
    return r;
  }
}
