// UbiFleet — Contrôle Véhicule (Angular 18)
import {
  Component, inject, OnInit, OnDestroy, ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, LowerCasePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin, Observable, of } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';
import { ControleApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { messageErreurApi } from '../../core/services/fenetre-saisie.service';
import { OptionsSaisieService } from '../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../shared/select-recherche/select-recherche.component';

interface Element {
  id: number; nom: string; categorie: string;
  categorie_display: string; ordre: number; actif: boolean; obligatoire: boolean;
}
interface Fiche {
  id: string; vehicule: string; vehicule_immat: string; chauffeur: string | null; chauffeur_nom: string | null;
  agence_nom: string; type_controle: string; type_controle_display: string;
  statut_global: string; statut_global_display: string;
  date_heure: string; kilometrage: number; est_validee: boolean;
  nb_points: number; nb_non_conformes: number; nb_photos: number;
}
interface PointState { statut: string; gravite: string; remarque: string; }

export const CATEGORIES_CONTROLE = [
  { value: 'moteur',         label: 'Moteur' },
  { value: 'securite',       label: 'Sécurité' },
  { value: 'carrosserie',    label: 'Carrosserie' },
  { value: 'eclairage',      label: 'Éclairage' },
  { value: 'pneumatiques',   label: 'Pneumatiques' },
  { value: 'interieur',      label: 'Intérieur' },
  { value: 'administratif',  label: 'Administratif' },
  { value: 'autre',          label: 'Autre' },
];
export const TYPES_CONTROLE = [
  { value: 'depart',           label: 'Contrôle départ' },
  { value: 'retour',           label: 'Contrôle retour' },
  { value: 'periodique',       label: 'Contrôle périodique' },
  { value: 'apres_sinistre',   label: 'Après sinistre' },
  { value: 'apres_reparation', label: 'Après réparation' },
];

/** Date locale au format attendu par <input type="datetime-local">. */
function maintenantLocal(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

@Component({
  selector: 'ubi-controle',
  standalone: true,
  imports: [RouterLink, DatePipe, LowerCasePipe, ReactiveFormsModule, SelectRechercheComponent],
  templateUrl: './controle.component.html',
  styleUrls:   ['./controle.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ControleComponent implements OnInit, OnDestroy {
  private api      = inject(ControleApiService);
  private options  = inject(OptionsSaisieService);
  private auth     = inject(AuthService);
  private router   = inject(Router);
  private fb       = inject(FormBuilder);
  private minuterie?: ReturnType<typeof setTimeout>;

  categories = CATEGORIES_CONTROLE;
  types      = TYPES_CONTROLE;
  peutParametrer = computed(() => this.auth.peutAcceder('parametres'));

  // ── Liste ──
  fiches        = signal<Fiche[]>([]);
  fichesTotal   = signal(0);
  fichesLoading = signal(false);
  stats         = signal<any>(null);
  message       = signal('');

  filtreImmat  = signal('');
  filtreType   = signal('');
  filtreStatut = signal('');
  filtreDebut  = signal('');
  filtreFin    = signal('');
  filtrePage   = signal(1);
  readonly pageSize = 20;
  nbFiltresActifs = computed(() =>
    [this.filtreImmat(), this.filtreType(), this.filtreStatut(), this.filtreDebut(), this.filtreFin()].filter(v => !!v).length);

  // ── Popup création / modification ──
  formOuvert   = signal(false);
  editId       = signal<string | null>(null);
  vehicules    = signal<OptionRecherche[]>([]);
  private kmVehicules: Record<string, number> = {};
  chauffeurs   = signal<OptionRecherche[]>([]);
  elements     = signal<Element[]>([]);
  pointsMap    = signal<Record<number, PointState>>({});
  photosNouvelles = signal<{ file: File; url: string }[]>([]);
  photosExistantes = signal<any[]>([]);
  enregistrement = signal(false);
  formErreur     = signal('');

  // ── Actions sur une fiche ──
  aSupprimer = signal<Fiche | null>(null);
  actionErreur = signal('');

  ficheForm = this.fb.group({
    vehicule:        ['', Validators.required],
    chauffeur:       [''],
    type_controle:   ['periodique', Validators.required],
    date_heure:      [maintenantLocal(), Validators.required],
    kilometrage:     [null as number | null, [Validators.required, Validators.min(0)]],
    notes_generales: [''],
  });

  elementsActifs = computed(() => this.elements().filter(e => e.actif));
  groupes = computed(() => this.categories
    .map(c => ({ ...c, elements: this.elementsActifs().filter(e => e.categorie === c.value) }))
    .filter(g => g.elements.length > 0));

  resumePoints = computed(() => {
    const pts = Object.values(this.pointsMap());
    return {
      nc: pts.filter(p => p.statut === 'non_conforme').length,
      sansGravite: pts.filter(p => p.statut === 'non_conforme' && !p.gravite).length,
      bloquants: pts.filter(p => p.gravite === 'bloquant').length,
    };
  });

  ngOnInit(): void {
    this.loadFiches();
    this.loadStats();
    this.api.getElements().subscribe({ next: l => this.elements.set(l), error: () => {} });
    this.options.vehicules().subscribe({
      next: l => { this.vehicules.set(l); l.forEach((v: any) => this.kmVehicules[v.value] = v.km ?? 0); },
      error: () => {},
    });
    this.options.chauffeurs().subscribe({ next: l => this.chauffeurs.set(l), error: () => {} });
  }

  ngOnDestroy(): void {
    clearTimeout(this.minuterie);
    clearTimeout(this.minuterieMessage);
    this.photosNouvelles().forEach(p => URL.revokeObjectURL(p.url));
  }

  // ── Liste ──
  private paramsFiltres(): Record<string, any> {
    const params: Record<string, any> = {};
    if (this.filtreImmat())  params['immatriculation'] = this.filtreImmat();
    if (this.filtreType())   params['type_controle']   = this.filtreType();
    if (this.filtreStatut() === 'a_valider') params['a_valider'] = 'true';
    else if (this.filtreStatut()) params['statut_global'] = this.filtreStatut();
    if (this.filtreDebut())  params['date_debut']      = this.filtreDebut();
    if (this.filtreFin())    params['date_fin']        = this.filtreFin();
    return params;
  }

  loadFiches(): void {
    this.fichesLoading.set(true);
    this.api.getFiches({ ...this.paramsFiltres(), page: this.filtrePage(), page_size: this.pageSize }).subscribe({
      next: (r: any) => {
        this.fiches.set(r.results ?? r ?? []);
        this.fichesTotal.set(r.count ?? 0);
        this.fichesLoading.set(false);
      },
      error: () => this.fichesLoading.set(false),
    });
  }

  loadStats(): void {
    this.api.getStatsFiches().subscribe({ next: s => this.stats.set(s), error: () => {} });
  }

  onFiltreInput(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement | HTMLSelectElement).value;
    const appliquer = () => {
      if (field === 'immat')  this.filtreImmat.set(val.trim());
      if (field === 'type')   this.filtreType.set(val);
      if (field === 'statut') this.filtreStatut.set(val);
      if (field === 'debut')  this.filtreDebut.set(val);
      if (field === 'fin')    this.filtreFin.set(val);
      this.filtrePage.set(1);
      this.loadFiches();
    };
    clearTimeout(this.minuterie);
    if (field === 'immat') this.minuterie = setTimeout(appliquer, 350); else appliquer();
  }

  filtrerStatut(statut: string): void {
    this.filtreStatut.set(this.filtreStatut() === statut ? '' : statut);
    this.filtrePage.set(1);
    this.loadFiches();
  }

  reinitialiserFiltres(): void {
    this.filtreImmat.set(''); this.filtreType.set(''); this.filtreStatut.set('');
    this.filtreDebut.set(''); this.filtreFin.set('');
    this.filtrePage.set(1);
    this.loadFiches();
  }

  allerPage(p: number): void { this.filtrePage.set(p); this.loadFiches(); }

  // ── Popup ──
  ouvrirFormulaire(f?: Fiche): void {
    this.formErreur.set('');
    this.viderPhotos();
    this.photosExistantes.set([]);
    this.editId.set(f?.id ?? null);
    const pts: Record<number, PointState> = {};
    for (const e of this.elementsActifs()) pts[e.id] = { statut: 'conforme', gravite: '', remarque: '' };
    if (!f) {
      this.ficheForm.reset({ vehicule: '', chauffeur: '', type_controle: 'periodique',
                             date_heure: maintenantLocal(), kilometrage: null, notes_generales: '' });
      this.pointsMap.set(pts);
      this.formOuvert.set(true);
      return;
    }
    this.api.getFiche(f.id).subscribe({
      next: (d: any) => {
        this.ficheForm.reset({
          vehicule: d.vehicule, chauffeur: d.chauffeur ?? '', type_controle: d.type_controle,
          date_heure: maintenantLocal(new Date(d.date_heure)), kilometrage: d.kilometrage,
          notes_generales: d.notes_generales ?? '',
        });
        for (const p of d.points ?? []) {
          pts[p.element] = { statut: p.statut, gravite: p.gravite ?? '', remarque: p.remarque ?? '' };
        }
        this.pointsMap.set(pts);
        this.photosExistantes.set(d.photos ?? []);
        this.formOuvert.set(true);
      },
      error: err => this.actionErreur.set(messageErreurApi(err, 'Fiche introuvable.')),
    });
  }

  fermerFormulaire(): void {
    if (this.enregistrement()) return;
    this.formOuvert.set(false);
    this.viderPhotos();
  }

  /** Véhicule choisi : kilométrage proposé = kilométrage actuel du véhicule. */
  onVehiculeChoisi(id: string): void {
    if (!this.editId() && id && !this.ficheForm.value.kilometrage) {
      this.ficheForm.patchValue({ kilometrage: this.kmVehicules[id] ?? null });
    }
  }

  pt(id: number): PointState {
    return this.pointsMap()[id] ?? { statut: 'conforme', gravite: '', remarque: '' };
  }

  setPoint(id: number, field: keyof PointState, val: string): void {
    const m = { ...this.pointsMap() };
    m[id] = { ...this.pt(id), [field]: val };
    if (field === 'statut' && val !== 'non_conforme') { m[id].gravite = ''; }
    this.pointsMap.set(m);
    if (this.formErreur() && !this.resumePoints().sansGravite) this.formErreur.set('');
  }

  toutConforme(): void {
    const m: Record<number, PointState> = {};
    for (const [id, p] of Object.entries(this.pointsMap())) m[+id] = { ...p, statut: 'conforme', gravite: '' };
    this.pointsMap.set(m);
  }

  onPhotos(e: Event): void {
    const input = e.target as HTMLInputElement;
    const ajout = Array.from(input.files ?? []).filter(f => f.type.startsWith('image/'));
    const trop = ajout.filter(f => f.size > 10 * 1024 * 1024);
    if (trop.length) this.formErreur.set(`Photo(s) trop volumineuse(s) (10 Mo maximum) : ${trop.map(f => f.name).join(', ')}`);
    this.photosNouvelles.set([...this.photosNouvelles(),
      ...ajout.filter(f => f.size <= 10 * 1024 * 1024).map(file => ({ file, url: URL.createObjectURL(file) }))]);
    input.value = '';
  }
  retirerPhoto(i: number): void {
    const l = [...this.photosNouvelles()];
    URL.revokeObjectURL(l[i].url);
    l.splice(i, 1);
    this.photosNouvelles.set(l);
  }
  supprimerPhotoExistante(ph: any): void {
    this.api.deletePhoto(ph.id).subscribe({
      next: () => this.photosExistantes.set(this.photosExistantes().filter(x => x.id !== ph.id)),
      error: err => this.formErreur.set(messageErreurApi(err, 'Suppression de la photo impossible.')),
    });
  }
  private viderPhotos(): void {
    this.photosNouvelles().forEach(p => URL.revokeObjectURL(p.url));
    this.photosNouvelles.set([]);
  }

  /** Enregistre la fiche, ses points et ses photos ; `valider` : valide ensuite. */
  enregistrer(valider: boolean): void {
    this.ficheForm.markAllAsTouched();
    if (this.ficheForm.invalid) { this.formErreur.set('Renseignez le véhicule, la date et le kilométrage.'); return; }
    if (this.resumePoints().sansGravite) { this.formErreur.set('Indiquez la gravité de chaque point non conforme.'); return; }
    this.enregistrement.set(true);
    this.formErreur.set('');
    const raw = this.ficheForm.getRawValue();
    const payload: any = {
      vehicule: raw.vehicule, chauffeur: raw.chauffeur || null, type_controle: raw.type_controle,
      date_heure: new Date(raw.date_heure as string).toISOString(),
      kilometrage: raw.kilometrage, notes_generales: raw.notes_generales || '',
    };
    const points = Object.entries(this.pointsMap()).map(([id, v]) => ({
      element: Number(id), statut: v.statut, gravite: v.gravite || null, remarque: v.remarque,
    }));
    const id = this.editId();
    let ficheId = id ?? '';
    const enregistrement$: Observable<any> = (id ? this.api.updateFiche(id, payload) : this.api.createFiche(payload)).pipe(
      switchMap((f: any) => { ficheId = f.id ?? id; this.editId.set(ficheId); return this.api.bulkSavePoints(ficheId, points); }),
      switchMap(() => {
        const envois = this.photosNouvelles().map(p => {
          const fd = new FormData();
          fd.append('fiche', ficheId); fd.append('image', p.file); fd.append('type_photo', 'autre');
          return this.api.uploadPhoto(ficheId, fd).pipe(map(() => null), catchError(() => of(p.file.name)));
        });
        return envois.length ? forkJoin(envois) : of([]);
      }),
      switchMap((echecs: any) => {
        const ko = (echecs as (string | null)[]).filter(Boolean);
        if (ko.length) throw { error: { detail: `Fiche enregistrée, mais photo(s) refusée(s) : ${ko.join(', ')}` } };
        return valider ? this.api.validerFiche(ficheId) : of(null);
      }),
    );
    enregistrement$.subscribe({
      next: (r: any) => {
        this.enregistrement.set(false);
        this.formOuvert.set(false);
        this.viderPhotos();
        this.message.set(valider ? `Fiche validée : ${r?.statut_display ?? ''}.` : 'Fiche enregistrée (en cours, à valider).');
        this.afficherMessage();
        this.loadFiches(); this.loadStats();
      },
      error: err => {
        this.enregistrement.set(false);
        this.viderPhotos();
        this.formErreur.set(messageErreurApi(err, "Erreur lors de l'enregistrement de la fiche."));
        this.loadFiches(); this.loadStats();
        // Les photos déjà envoyées apparaissent dans la fiche
        if (this.editId()) this.api.getFiche(this.editId()!).subscribe({ next: (d: any) => this.photosExistantes.set(d.photos ?? []) });
      },
    });
  }

  validerFiche(f: Fiche): void {
    this.actionErreur.set('');
    this.api.validerFiche(f.id).subscribe({
      next: (r: any) => {
        this.message.set(`Fiche ${f.vehicule_immat} validée : ${r.statut_display}.`);
        this.afficherMessage();
        this.loadFiches(); this.loadStats();
      },
      error: err => this.actionErreur.set(messageErreurApi(err, 'Validation impossible.')),
    });
  }

  confirmerSuppression(): void {
    const f = this.aSupprimer();
    if (!f) return;
    this.api.deleteFiche(f.id).subscribe({
      next: () => { this.aSupprimer.set(null); this.loadFiches(); this.loadStats(); },
      error: err => { this.aSupprimer.set(null); this.actionErreur.set(messageErreurApi(err, 'Suppression impossible.')); },
    });
  }

  private minuterieMessage?: ReturnType<typeof setTimeout>;
  private afficherMessage(): void {
    clearTimeout(this.minuterieMessage);
    this.minuterieMessage = setTimeout(() => this.message.set(''), 6000);
  }

  voirRapport(id: string): void { this.router.navigate(['/controle', id]); }

  // ── Helpers ──
  statutClass(s: string): string {
    const m: Record<string, string> = {
      conforme: 'badge-green', non_conforme: 'badge-danger', partiel: 'badge-warning', en_cours: 'badge-gray'
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

  totalPages = computed(() => Math.ceil(this.fichesTotal() / this.pageSize) || 1);
  pages = computed(() => {
    const t = this.totalPages(), c = this.filtrePage(), r: number[] = [];
    for (let i = Math.max(1, c - 2); i <= Math.min(t, c + 2); i++) r.push(i);
    return r;
  });
}
