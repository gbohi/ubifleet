// UbiFleet — Paramètres Component (Angular 18)
import { GroupeHub, HubCartesComponent } from '../../shared/hub-cartes/hub-cartes.component';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed, DestroyRef
} from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { CarburantApiService, EntretienApiService, ParametrageApiService, SinistreApiService, AgenceApiService, VehiculeApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { TypesMouvementService } from '../../core/services/types-mouvement.service';
import { Prestataire, Assureur, Agence } from '../../core/models';
import { SeuilsComponent } from './seuils/seuils.component';
import { CircuitsValidationComponent } from './circuits-validation/circuits-validation.component';
import { ElementsControleComponent } from './elements-controle/elements-controle.component';
import { PrixCarburantComponent } from './prix-carburant/prix-carburant.component';
import { FenetreSaisieComponent } from './fenetre-saisie/fenetre-saisie.component';
import { ReferentielSimpleComponent } from './referentiel-simple/referentiel-simple.component';

export type Section =
  | 'echeances' | 'saisie' | 'carburant' | 'stations'
  | 'marques' | 'types_vehicule' | 'statuts' | 'affectations' | 'types_doc' | 'types_mouvement'
  | 'agences' | 'tournees'
  | 'types' | 'prestataires' | 'assureurs' | 'types_sinistre' | 'types_contrat' | 'categories_depense'
  | 'circuits' | 'elements';


@Component({
  selector: 'ubi-parametres',
  standalone: true,
  imports: [HubCartesComponent, ReactiveFormsModule, DecimalPipe, DatePipe, SeuilsComponent, CircuitsValidationComponent, ElementsControleComponent, PrixCarburantComponent, FenetreSaisieComponent, ReferentielSimpleComponent],
  templateUrl: './parametres.component.html',
  styleUrls: ['./parametres.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ParametresComponent implements OnInit {
  private fb             = inject(FormBuilder);
  private entretienApi   = inject(EntretienApiService);
  private parametrageApi = inject(ParametrageApiService);
  private typesMvtCache  = inject(TypesMouvementService);
  private sinistreApi    = inject(SinistreApiService);
  private vehiculeApi    = inject(VehiculeApiService);
  private agenceApi      = inject(AgenceApiService);
  private carburantApi   = inject(CarburantApiService);
  private auth           = inject(AuthService);
  private route          = inject(ActivatedRoute);
  private router         = inject(Router);
  private destroyRef     = inject(DestroyRef);

  // ── Rubriques (accueil en cartes) ──
  readonly navigation: GroupeHub[] = [
    { titre: 'Règles & seuils', icone: 'fas fa-sliders-h', teinte: 'bleu', cartes: [
      { cle: 'echeances', libelle: 'Échéances', icone: 'fas fa-bell',
        description: "Seuils d'alerte : révision, pneus, documents, contrôle technique" },
      { cle: 'saisie', libelle: 'Fenêtre de saisie', icone: 'fas fa-calendar-check',
        description: 'Délai de saisie des relevés et prises, corrections tardives' },
    ]},
    { titre: 'Carburant', icone: 'fas fa-gas-pump', teinte: 'orange', cartes: [
      { cle: 'carburant', libelle: 'Prix & consommation', icone: 'fas fa-gas-pump',
        description: 'Prix du litre et historique, seuils de consommation' },
      { cle: 'stations', libelle: 'Stations', icone: 'fas fa-charging-station',
        description: 'Stations-service proposées dans les prises de carburant' },
    ]},
    { titre: 'Parc automobile', icone: 'fas fa-car', teinte: 'vert', cartes: [
      { cle: 'marques', libelle: 'Marques & modèles', icone: 'fas fa-car-side',
        description: 'Constructeurs et modèles des véhicules' },
      { cle: 'types_vehicule', libelle: 'Types de véhicule', icone: 'fas fa-truck-pickup',
        description: 'Berline, pick-up, camion…' },
      { cle: 'statuts', libelle: 'Statuts véhicule', icone: 'fas fa-circle',
        description: 'En service, en panne, en révision… (historisés)' },
      { cle: 'affectations', libelle: 'Affectations / usages', icone: 'fas fa-tag',
        description: 'Usage du véhicule : livraison, direction, commercial…' },
      { cle: 'types_doc', libelle: 'Types de documents', icone: 'fas fa-file-alt',
        description: 'Carte grise, visite technique, vignette…' },
      { cle: 'types_mouvement', libelle: 'Types de mouvement', icone: 'fas fa-exchange-alt',
        description: 'Tournée, course, mission… des relevés et des prises' },
    ]},
    { titre: 'Organisation', icone: 'fas fa-sitemap', teinte: 'violet', cartes: [
      { cle: 'agences', libelle: 'Agences', icone: 'fas fa-map-marker-alt',
        description: 'Sites, codes et numéros client Total' },
      { cle: 'tournees', libelle: 'Tournées', icone: 'fas fa-route',
        description: 'Circuits de livraison et dotation théorique' },
    ]},
    { titre: 'Entretien & assurance', icone: 'fas fa-tools', teinte: 'rouge', cartes: [
      { cle: 'types', libelle: "Types d'intervention", icone: 'fas fa-wrench',
        description: 'Vidange, réparation, pneus… et leur périodicité' },
      { cle: 'prestataires', libelle: 'Prestataires / garages', icone: 'fas fa-tools',
        description: 'Garages et prestataires des interventions' },
      { cle: 'assureurs', libelle: 'Assureurs', icone: 'fas fa-shield-alt',
        description: 'Compagnies et contacts sinistres' },
      { cle: 'types_contrat', libelle: "Types de contrat d'assurance", icone: 'fas fa-file-contract',
        description: 'Responsabilité civile, tous risques…' },
      { cle: 'types_sinistre', libelle: 'Types de sinistre', icone: 'fas fa-car-crash',
        description: 'Accident, vol, bris de glace…' },
    ]},
    { titre: 'Budget', icone: 'fas fa-coins', teinte: 'orange', cartes: [
      { cle: 'categories_depense', libelle: 'Catégories de dépense', icone: 'fas fa-coins',
        description: 'Nature des dépenses et poste du budget' },
    ]},
    { titre: 'Workflows', icone: 'fas fa-project-diagram', teinte: 'gris', cartes: [
      { cle: 'circuits', libelle: 'Circuits de validation', icone: 'fas fa-sitemap',
        description: 'Étapes et valideurs des demandes' },
      { cle: 'elements', libelle: 'Éléments de contrôle', icone: 'fas fa-clipboard-check',
        description: 'Points vérifiés lors des contrôles véhicule' },
    ]},
  ];
  private readonly sections = this.navigation.flatMap(g => g.cartes.map(c => c.cle as Section));

  /** Rubrique ouverte ; null = accueil en cartes. */
  section   = signal<Section | null>(null);
  recherche = signal('');
  notice    = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);

  /** Thème et libellé de la rubrique ouverte (fil d'Ariane). */
  rubrique = computed(() => {
    for (const g of this.navigation) {
      const c = g.cartes.find(x => x.cle === this.section());
      if (c) return { groupe: g.titre, libelle: c.libelle };
    }
    return null;
  });

  /** Nombre d'éléments affiché à côté de chaque rubrique de la navigation. */
  compteurs = computed<Partial<Record<Section, number>>>(() => ({
    marques: this.marques().length, statuts: this.statutsVehicule().length,
    affectations: this.affectations().length, types_doc: this.typesDoc().length,
    agences: this.agences().length, tournees: this.tournees().length,
    types: this.types().length, prestataires: this.prestataires().length,
    assureurs: this.assureurs().length,
    stations: this.stations().length, types_mouvement: this.typesMouvement().length,
    types_vehicule: this.nbTypesVehicule(),
    ...this.nbReferentiels(),
  }));
  /** Nombre d'éléments des référentiels à code (remonté par chaque écran). */
  nbReferentiels = signal<Record<string, number>>({});
  majCompte(section: string, n: number): void { this.nbReferentiels.update(c => ({ ...c, [section]: n })); }

  /** Nombre d'éléments des référentiels à code, pour les cartes de l'accueil. */
  private chargerComptesReferentiels(): void {
    const sources: [string, Observable<any[]>][] = [
      ['types_vehicule', this.parametrageApi.getTypesVehicule()],
      ['categories_depense', this.parametrageApi.getCategoriesDepense()],
      ['types_sinistre', this.parametrageApi.getTypesSinistre()],
      ['types_contrat', this.parametrageApi.getTypesContrat()],
    ];
    for (const [cle, obs] of sources) {
      obs.subscribe({ next: l => cle === 'types_vehicule' ? this.nbTypesVehicule.set(l.length) : this.majCompte(cle, l.length), error: () => {} });
    }
  }

  /** Postes du budget annuel : chaque catégorie de dépense est imputée sur l'un d'eux. */
  readonly champsCategorie = [{
    cle: 'poste_budget', libelle: 'Poste du budget',
    aide: 'Ligne du budget annuel sur laquelle ces dépenses sont comptées (budget prévu / réalisé).',
    options: [
      { value: 'carburant', label: 'Carburant' }, { value: 'entretien', label: 'Entretien' },
      { value: 'reparations', label: 'Réparations' }, { value: 'assurances', label: 'Assurances' },
      { value: 'pneumatiques', label: 'Pneumatiques' }, { value: 'divers', label: 'Divers' },
    ],
  }];
  /** Nombre de types de véhicule (remonté par le référentiel). */
  nbTypesVehicule = signal(0);

  // Droits d'écriture (calculés par l'API, cf. /auth/me/acces/)
  ecritureReferentiels = computed(() => this.auth.peutAcceder('referentiels_ecriture'));
  ecritureSeuils       = computed(() => this.auth.peutAcceder('parametres'));
  ecritureCircuits     = computed(() => this.auth.peutAcceder('circuits_ecriture'));
  ecritureElements     = computed(() => this.auth.peutAcceder('elements_controle_ecriture'));

  allerA(section: Section | string | null): void {
    this.section.set(section as Section | null);
    this.recherche.set('');
    this.notice.set(null);
    // Historique du navigateur : « Précédent » revient à l'accueil des paramètres
    this.router.navigate([], { relativeTo: this.route, queryParams: { section: section || null } });
  }

  /** Filtre une liste sur les champs donnés selon la recherche en cours. */
  filtrer<T extends Record<string, any>>(liste: T[], ...champs: string[]): T[] {
    const q = this.recherche().trim().toLowerCase();
    if (!q) return liste;
    return liste.filter(x => champs.some(c => String(x[c] ?? '').toLowerCase().includes(q)));
  }

  /** Active / désactive un élément directement depuis la liste. */
  basculer(req: Observable<any>, recharger: () => void): void {
    req.subscribe({
      next: () => recharger(),
      error: (err: any) => this.notice.set({ type: 'err', texte: err?.error?.detail ?? 'Modification impossible.' }),
    });
  }

  basculerStatut(x: any): void      { this.basculer(this.parametrageApi.updateStatutVehicule(x.id, { actif: !x.actif }), () => this.loadStatutsVehicule()); }
  basculerAffectation(x: any): void { this.basculer(this.parametrageApi.updateAffectation(x.id, { actif: !x.actif }), () => this.loadAffectations()); }
  basculerMarque(x: any): void      { this.basculer(this.parametrageApi.updateMarque(x.id, { actif: !x.actif }), () => this.loadMarques()); }
  basculerModele(x: any): void      { this.basculer(this.parametrageApi.updateModele(x.id, { actif: !x.actif }), () => this.loadModeles()); }
  basculerTournee(x: any): void     { this.basculer(this.parametrageApi.updateTournee(x.id, { actif: !x.actif }), () => this.loadTournees()); }
  basculerTypeDoc(x: any): void     { this.toggleActifTypesDoc(x); }
  basculerType(x: any): void        { this.basculer(this.entretienApi.updateType(x.id, { is_active: !x.is_active }), () => this.loadTypes()); }
  basculerPrestataire(x: any): void { this.basculer(this.entretienApi.updatePrestataire(x.id, { is_active: !x.is_active } as any), () => this.loadPrestataires()); }
  basculerAssureur(x: any): void    { this.basculer(this.sinistreApi.updateAssureur(x.id, { is_active: !x.is_active } as any), () => this.loadAssureurs()); }
  basculerAgence(x: any): void      { this.basculer(this.agenceApi.update(x.id, { is_active: !x.is_active } as any), () => this.loadAgences()); }

  /** Dernier message de succès d'une fenêtre de saisie, affiché dans la rubrique. */
  succes = computed(() => [
    this.typesSuccess(), this.agencesSuccess(), this.assureursSuccess(), this.prestairesSuccess(),
    this.typesDocSuccess(), this.tourneesSuccess(), this.affectationsSuccess(),
    this.statutsVehiculeSuccess(), this.marquesSuccess(), this.modelesSuccess(),
  ].find(m => !!m) ?? '');

  private erreurSuppression(err: any): void {
    this.notice.set({ type: 'err', texte: err?.error?.detail ?? 'Suppression impossible.' });
  }

  // ── Types d'intervention ──
  types         = signal<any[]>([]);
  typesSaving   = signal(false);
  typesSuccess  = signal('');
  typesError    = signal('');
  editTypeId    = signal<string | null>(null);
  showTypesModal = signal(false);

  typeForm = this.fb.group({
    nom:              ['', Validators.required],
    categorie:        ['preventif', Validators.required],
    periodicite_km:   [0],
    periodicite_mois: [0],
  });

  get tf() { return this.typeForm.controls; }

  readonly categoriesType = [
    { value: 'preventif',   label: 'Entretien préventif' },
    { value: 'curatif',     label: 'Réparation curative' },
    { value: 'pneus',       label: 'Pneus' },
    { value: 'carrosserie', label: 'Carrosserie' },
    { value: 'controle',    label: 'Contrôle réglementaire' },
    { value: 'autre',       label: 'Autre' },
  ];

  // ── Agences ──
  agences         = signal<Agence[]>([]);
  agencesLoad     = signal(false);
  agencesSuccess  = signal('');
  agencesError    = signal('');
  editAgenceId    = signal<string | null>(null);
  showAgenceModal = signal(false);

  agenceForm = this.fb.group({
    nom:                  ['', Validators.required],
    code:                 ['', Validators.required],
    ville:                ['', Validators.required],
    adresse:              [''],
    telephone:            [''],
    responsable_nom:      [''],
    numero_client_total:  [''],
    is_active:            [true],
  });

  get agf() { return this.agenceForm.controls; }

  // ── Assureurs ──
  assureurs          = signal<Assureur[]>([]);
  assureursLoad      = signal(false);
  assureursSuccess   = signal('');
  assureursError     = signal('');
  editAssureurId     = signal<string | null>(null);
  showAssureurModal  = signal(false);

  assureurForm = this.fb.group({
    nom:              ['', Validators.required],
    telephone:        [''],
    email:            ['', Validators.email],
    adresse:          [''],
    contact_sinistre: [''],
  });

  get af2() { return this.assureurForm.controls; }

  // ── Prestataires ──
  prestataires       = signal<Prestataire[]>([]);
  prestairesSaving   = signal(false);
  prestairesSuccess  = signal('');
  prestairesError    = signal('');
  editPrestaireId    = signal<string | null>(null);
  showPrestaireModal = signal(false);

  prestataireForm = this.fb.group({
    nom:          ['', Validators.required],
    specialite:   [''],
    telephone:    [''],
    email:        ['', Validators.email],
    ville:        [''],
    adresse:      [''],
    note_qualite: [null as number | null],
  });

  get pf() { return this.prestataireForm.controls; }

  // ── Types de documents véhicule ──
  typesDoc          = signal<any[]>([]);
  typesDocLoading   = signal(false);
  typesDocError     = signal('');
  typesDocSuccess   = signal('');
  editTypesDocId    = signal<number | null>(null);
  showTypesDocModal = signal(false);
  typesDocForm = this.fb.group({
    libelle: ['', Validators.required],
    ordre:   [0],
    actif:   [true],
  });

  ngOnInit(): void {
    // Rubrique de l'URL (?section=…), suivie aussi par « Précédent / Suivant »
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(q => {
      const demandee = q.get('section') as Section | null;
      this.section.set(demandee && this.sections.includes(demandee) ? demandee : null);
    });
    this.chargerComptesReferentiels();
    this.loadTypes();
    this.loadTypesDoc();
    this.loadPrestataires();
    this.loadAssureurs();
    this.loadAgences();
    this.loadTournees();
    this.loadAffectations();
    this.loadMarques();
    this.loadModeles();
    this.loadStatutsVehicule();
    this.loadStations();
    this.loadTypesMouvement();
  }

  // ── Types ──
  loadTypes(): void {
    this.entretienApi.getTypes({ tous: 1, page_size: 500 }).subscribe({
      next: (list) => this.types.set(Array.isArray(list) ? list : []),
      error: () => this.types.set([]),
    });
  }

  ouvrirNouveauType(): void {
    this.editTypeId.set(null); this.typesError.set('');
    this.typeForm.reset({ categorie: 'preventif', periodicite_km: 0, periodicite_mois: 0 });
    this.showTypesModal.set(true);
  }
  editType(type: any): void {
    this.editTypeId.set(type.id); this.typesError.set('');
    this.typeForm.patchValue({ nom: type.nom, categorie: type.categorie,
      periodicite_km: type.periodicite_km, periodicite_mois: type.periodicite_mois });
    this.showTypesModal.set(true);
  }
  cancelEditType(): void {
    this.editTypeId.set(null); this.showTypesModal.set(false);
    this.typeForm.reset({ categorie: 'preventif', periodicite_km: 0, periodicite_mois: 0 });
    this.typesError.set('');
  }
  saveType(): void {
    if (this.typeForm.invalid || this.typesSaving()) return;
    this.typesSaving.set(true); this.typesError.set('');
    const payload = this.typeForm.value;
    const req = this.editTypeId()
      ? this.entretienApi.updateType(this.editTypeId()!, payload)
      : this.entretienApi.createType(payload);
    req.subscribe({
      next: () => {
        this.typesSaving.set(false);
        this.typesSuccess.set(this.editTypeId() ? 'Type modifié.' : 'Type créé.');
        this.cancelEditType(); this.loadTypes();
      },
      error: () => { this.typesSaving.set(false); this.typesError.set("Erreur lors de l'enregistrement."); },
    });
  }

  deleteType(id: string): void {
    if (!confirm('Supprimer ce type d\'intervention ?')) return;
    this.entretienApi.deleteType(id).subscribe({
      next: () => this.loadTypes(),
      error: (err) => this.erreurSuppression(err),
    });
  }

  // ── Agences ──
  loadAgences(): void {
    this.agencesLoad.set(true);
    this.agenceApi.getAll().subscribe({
      next: (res: any) => {
        this.agences.set(Array.isArray(res) ? res : (res.results ?? []));
        this.agencesLoad.set(false);
      },
      error: () => this.agencesLoad.set(false),
    });
  }

  ouvrirNouvelleAgence(): void {
    this.editAgenceId.set(null); this.agencesError.set('');
    this.agenceForm.reset({ is_active: true });
    this.agf['code'].enable();
    this.showAgenceModal.set(true);
  }
  editAgence(a: Agence): void {
    this.editAgenceId.set(a.id);
    this.agenceForm.patchValue({ nom: a.nom, code: a.code, ville: a.ville,
      adresse: a.adresse, telephone: a.telephone, responsable_nom: a.responsable_nom,
      numero_client_total: (a as any).numero_client_total ?? '', is_active: a.is_active });
    this.agf['code'].disable();
    this.agencesError.set(''); this.agencesSuccess.set('');
    this.showAgenceModal.set(true);
  }
  cancelEditAgence(): void {
    this.editAgenceId.set(null); this.showAgenceModal.set(false);
    this.agenceForm.reset({ is_active: true }); this.agf['code'].enable();
  }

  saveAgence(): void {
    if (this.agenceForm.invalid || this.agencesLoad()) return;
    this.agencesLoad.set(true);
    this.agencesError.set('');
    const raw = this.agenceForm.getRawValue();

    const req = this.editAgenceId()
      ? this.agenceApi.update(this.editAgenceId()!, raw as any)
      : this.agenceApi.create(raw as any);

    req.subscribe({
      next: () => {
        this.agencesLoad.set(false);
        this.agencesSuccess.set(this.editAgenceId() ? 'Agence modifiée.' : 'Agence créée.');
        this.cancelEditAgence();
        this.loadAgences();
      },
      error: (err: any) => {
        this.agencesLoad.set(false);
        this.agencesError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement.");
      },
    });
  }

  deleteAgence(id: string): void {
    if (!confirm('Supprimer cette agence ?')) return;
    this.agenceApi.delete(id).subscribe({
      next: () => this.loadAgences(),
      error: (err) => this.erreurSuppression(err),
    });
  }

  // ── Assureurs ──
  loadAssureurs(): void {
    this.assureursLoad.set(true);
    this.sinistreApi.getAssureurs({ tous: 1 }).subscribe({
      next: (list) => {
        this.assureurs.set(Array.isArray(list) ? list : []);
        this.assureursLoad.set(false);
      },
      error: () => this.assureursLoad.set(false),
    });
  }

  ouvrirNouvelAssureur(): void {
    this.editAssureurId.set(null); this.assureursError.set(''); this.assureurForm.reset();
    this.showAssureurModal.set(true);
  }
  editAssureur(a: Assureur): void {
    this.editAssureurId.set(a.id); this.assureursError.set(''); this.assureursSuccess.set('');
    this.assureurForm.patchValue({ nom: a.nom, telephone: a.telephone,
      email: a.email, adresse: a.adresse, contact_sinistre: a.contact_sinistre });
    this.showAssureurModal.set(true);
  }
  cancelEditAssureur(): void {
    this.editAssureurId.set(null); this.showAssureurModal.set(false); this.assureurForm.reset();
  }

  saveAssureur(): void {
    if (this.assureurForm.invalid || this.assureursLoad()) return;
    this.assureursLoad.set(true);
    this.assureursError.set('');

    const raw = this.assureurForm.value;
    const payload: Partial<Assureur> = {
      nom:              raw.nom              ?? undefined,
      telephone:        raw.telephone        ?? undefined,
      email:            raw.email            ?? undefined,
      adresse:          raw.adresse          ?? undefined,
      contact_sinistre: raw.contact_sinistre ?? undefined,
    };

    const req = this.editAssureurId()
      ? this.sinistreApi.updateAssureur(this.editAssureurId()!, payload)
      : this.sinistreApi.createAssureur(payload);

    req.subscribe({
      next: () => {
        this.assureursLoad.set(false);
        this.assureursSuccess.set(this.editAssureurId() ? 'Assureur modifié.' : 'Assureur créé.');
        this.cancelEditAssureur();
        this.loadAssureurs();
      },
      error: (err) => {
        this.assureursLoad.set(false);
        this.assureursError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement.");
      },
    });
  }

  deleteAssureur(id: string): void {
    if (!confirm('Supprimer cet assureur ?')) return;
    this.sinistreApi.deleteAssureur(id).subscribe({
      next: () => this.loadAssureurs(),
      error: (err) => this.erreurSuppression(err),
    });
  }

  // ── Prestataires ──
  loadPrestataires(): void {
    this.entretienApi.getPrestataires({ page_size: 500, tous: 1 }).subscribe({
      next: (res) => this.prestataires.set(res.results ?? []),
      error: () => this.prestataires.set([]),
    });
  }

  ouvrirNouveauPrestataire(): void {
    this.editPrestaireId.set(null); this.prestataireForm.reset();
    this.showPrestaireModal.set(true);
  }
  editPrestataire(p: Prestataire): void {
    this.editPrestaireId.set(p.id);
    this.prestataireForm.patchValue({ nom: p.nom, specialite: p.specialite,
      telephone: p.telephone, email: p.email, ville: p.ville,
      adresse: p.adresse, note_qualite: p.note_qualite });
    this.showPrestaireModal.set(true);
  }
  cancelEditPrestataire(): void {
    this.editPrestaireId.set(null); this.showPrestaireModal.set(false); this.prestataireForm.reset();
  }

  savePrestataire(): void {
    if (this.prestataireForm.invalid || this.prestairesSaving()) return;
    this.prestairesSaving.set(true);
    this.prestairesError.set('');

    const raw = this.prestataireForm.value;
    const payload: Partial<Prestataire> = {
      nom:          raw.nom          ?? undefined,
      specialite:   raw.specialite   ?? undefined,
      telephone:    raw.telephone    ?? undefined,
      email:        raw.email        ?? undefined,
      ville:        raw.ville        ?? undefined,
      adresse:      raw.adresse      ?? undefined,
      note_qualite: raw.note_qualite ?? undefined,
    };
    const req = this.editPrestaireId()
      ? this.entretienApi.updatePrestataire(this.editPrestaireId()!, payload)
      : this.entretienApi.createPrestataire(payload);

    req.subscribe({
      next: () => {
        this.prestairesSaving.set(false);
        this.prestairesSuccess.set(this.editPrestaireId() ? 'Prestataire modifié.' : 'Prestataire créé.');
        this.cancelEditPrestataire();
        this.loadPrestataires();
      },
      error: () => {
        this.prestairesSaving.set(false);
        this.prestairesError.set('Erreur lors de l\'enregistrement.');
      },
    });
  }

  deletePrestataire(id: string): void {
    if (!confirm('Supprimer ce prestataire ?')) return;
    this.entretienApi.deletePrestataire(id).subscribe({
      next: () => this.loadPrestataires(),
      error: (err) => this.erreurSuppression(err),
    });
  }

  // ── Types de documents véhicule ──────────────────────────────
  loadTypesDoc(): void {
    this.typesDocLoading.set(true);
    this.vehiculeApi.getTypesDocument().subscribe({
      next: (list) => { this.typesDoc.set(list ?? []); this.typesDocLoading.set(false); },
      error: () => this.typesDocLoading.set(false),
    });
  }

  ouvrirNouveauTypeDoc(): void {
    this.editTypesDocId.set(null); this.typesDocError.set('');
    this.typesDocForm.reset({ libelle: '', ordre: 0, actif: true });
    this.showTypesDocModal.set(true);
  }
  editTypesDoc(t: any): void {
    this.editTypesDocId.set(t.id);
    this.typesDocForm.patchValue({ libelle: t.libelle, ordre: t.ordre, actif: t.actif });
    this.showTypesDocModal.set(true);
  }
  cancelEditTypesDoc(): void {
    this.editTypesDocId.set(null); this.showTypesDocModal.set(false);
    this.typesDocForm.reset({ libelle: '', ordre: 0, actif: true });
  }

  saveTypesDoc(): void {
    if (this.typesDocForm.invalid) return;
    const data = this.typesDocForm.value;
    const id   = this.editTypesDocId();
    const req  = id
      ? this.vehiculeApi.updateTypeDocument(id, data)
      : this.vehiculeApi.createTypeDocument(data);

    req.subscribe({
      next: () => {
        this.typesDocSuccess.set(id ? 'Type modifié.' : 'Type créé.');
        this.cancelEditTypesDoc();
        this.loadTypesDoc();
        setTimeout(() => this.typesDocSuccess.set(''), 3000);
      },
      error: (err) => this.typesDocError.set(err?.error?.detail ?? 'Erreur.'),
    });
  }

  toggleActifTypesDoc(t: any): void {
    this.vehiculeApi.updateTypeDocument(t.id, { actif: !t.actif }).subscribe({
      next: () => this.loadTypesDoc(),
      error: () => {},
    });
  }

  deleteTypesDoc(t: any): void {
    if (!confirm(`Supprimer le type "${t.libelle}" ?`)) return;
    this.vehiculeApi.deleteTypeDocument(t.id).subscribe({
      next: () => this.loadTypesDoc(),
      error: (err) => this.typesDocError.set(err?.error?.detail ?? 'Impossible de supprimer.'),
    });
  }

  // ── Tournées ────────────────────────────────────────────────────
  tournees             = signal<any[]>([]);
  tourneesLoad         = signal(false);
  tourneesError        = signal('');
  tourneesSuccess      = signal('');
  editTourneeId        = signal<number | null>(null);
  showTourneeModal     = signal(false);
  deleteTourneeConfirm = signal<any>(null);

  tourneeForm = this.fb.group({
    code:          ['', Validators.required],
    libelle:       ['', Validators.required],
    agence:        [null as string | null, Validators.required],
    dotation:      [0, [Validators.required, Validators.min(0)]],
    km_theorique:  [0, [Validators.required, Validators.min(0)]],
    actif:         [true],
  });

  // Filtre agence sur la liste des tournées
  tourneeFiltreAgence = signal('');
  tourneesFiltrees = computed(() => {
    const ag = this.tourneeFiltreAgence();
    if (!ag) return this.tournees();
    return this.tournees().filter((t: any) => t.agence === ag);
  });

  loadTournees(): void {
    this.tourneesLoad.set(true);
    this.parametrageApi.getTournees().subscribe({
      next: (list) => { this.tournees.set(list); this.tourneesLoad.set(false); },
      error: () => this.tourneesLoad.set(false),
    });
  }

  ouvrirNouvelleTournee(): void {
    this.editTourneeId.set(null);
    this.tourneesError.set('');
    this.tourneeForm.reset({ agence: null, dotation: 0, km_theorique: 0, actif: true });
    this.tourneeForm.controls.dotation.enable();
    this.showTourneeModal.set(true);
  }

  editTournee(t: any): void {
    // La dotation ne se modifie que par une demande validée (bouton « Dotation »)
    this.tourneeForm.controls.dotation.disable();
    this.editTourneeId.set(t.id);
    this.tourneesError.set('');
    this.tourneeForm.patchValue({
      code: t.code, libelle: t.libelle, agence: t.agence,
      dotation: t.dotation, km_theorique: t.km_theorique, actif: t.actif,
    });
    this.showTourneeModal.set(true);
  }

  cancelEditTournee(): void {
    this.editTourneeId.set(null);
    this.showTourneeModal.set(false);
    this.tourneeForm.reset({ agence: null, dotation: 0, km_theorique: 0, actif: true });
    this.tourneesError.set('');
  }

  saveTournee(): void {
    if (this.tourneeForm.invalid) return;
    const id  = this.editTourneeId();
    const req = id
      ? this.parametrageApi.updateTournee(id, this.tourneeForm.value)
      : this.parametrageApi.createTournee(this.tourneeForm.value);
    req.subscribe({
      next: () => {
        this.tourneesSuccess.set(id ? 'Tournée modifiée.' : 'Tournée créée.');
        this.cancelEditTournee();
        this.loadTournees();
        setTimeout(() => this.tourneesSuccess.set(''), 3000);
      },
      error: (err: any) => this.tourneesError.set(err?.error?.detail ?? 'Erreur.'),
    });
  }

  demanderSuppressionTournee(t: any): void  { this.deleteTourneeConfirm.set(t); }
  annulerSuppressionTournee(): void          { this.deleteTourneeConfirm.set(null); }

  confirmerSuppressionTournee(): void {
    const t = this.deleteTourneeConfirm();
    if (!t) return;
    this.parametrageApi.deleteTournee(t.id).subscribe({
      next: () => { this.deleteTourneeConfirm.set(null); this.loadTournees(); },
      error: (err: any) => {
        this.erreurSuppression(err);
        this.deleteTourneeConfirm.set(null);
      },
    });
  }

  // ── Affectations / Usages ─────────────────────────────────────────
  affectations          = signal<any[]>([]);
  affectationsLoad      = signal(false);
  affectationsError     = signal('');
  affectationsSuccess   = signal('');
  editAffectationId     = signal<number | null>(null);
  showAffectationModal  = signal(false);
  deleteAffectationConfirm = signal<any>(null);

  affectationForm = this.fb.group({
    code:    ['', Validators.required],
    libelle: ['', Validators.required],
    actif:   [true],
  });

  loadAffectations(): void {
    this.affectationsLoad.set(true);
    this.parametrageApi.getAffectations().subscribe({
      next: (l) => { this.affectations.set(l); this.affectationsLoad.set(false); },
      error: () => this.affectationsLoad.set(false),
    });
  }

  ouvrirNouvelleAffectation(): void {
    this.editAffectationId.set(null);
    this.affectationsError.set('');
    this.affectationForm.reset({ actif: true });
    this.showAffectationModal.set(true);
  }

  editAffectation(a: any): void {
    this.editAffectationId.set(a.id);
    this.affectationsError.set('');
    this.affectationForm.patchValue({ code: a.code, libelle: a.libelle, actif: a.actif });
    this.showAffectationModal.set(true);
  }

  cancelEditAffectation(): void {
    this.editAffectationId.set(null);
    this.showAffectationModal.set(false);
    this.affectationForm.reset({ actif: true });
    this.affectationsError.set('');
  }

  saveAffectation(): void {
    if (this.affectationForm.invalid) return;
    const id  = this.editAffectationId();
    const req = id
      ? this.parametrageApi.updateAffectation(id, this.affectationForm.value)
      : this.parametrageApi.createAffectation(this.affectationForm.value);
    req.subscribe({
      next: () => {
        this.affectationsSuccess.set(id ? 'Affectation modifiée.' : 'Affectation créée.');
        this.cancelEditAffectation();
        this.loadAffectations();
        setTimeout(() => this.affectationsSuccess.set(''), 3000);
      },
      error: (err: any) => this.affectationsError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  demanderSuppressionAffectation(a: any): void { this.deleteAffectationConfirm.set(a); }
  annulerSuppressionAffectation(): void         { this.deleteAffectationConfirm.set(null); }

  confirmerSuppressionAffectation(): void {
    const a = this.deleteAffectationConfirm();
    if (!a) return;
    this.parametrageApi.deleteAffectation(a.id).subscribe({
      next: () => { this.deleteAffectationConfirm.set(null); this.loadAffectations(); },
      error: (err: any) => {
        this.erreurSuppression(err);
        this.deleteAffectationConfirm.set(null);
      },
    });
  }

  // ── Statuts véhicule ──────────────────────────────────────────────
  statutsVehicule          = signal<any[]>([]);
  statutsVehiculeLoad      = signal(false);
  statutsVehiculeError     = signal('');
  statutsVehiculeSuccess   = signal('');
  editStatutVehiculeId     = signal<number | null>(null);
  showStatutVehiculeModal  = signal(false);
  deleteStatutVehiculeConfirm = signal<any>(null);

  statutVehiculeForm = this.fb.group({
    code:    ['', Validators.required],
    libelle: ['', Validators.required],
    couleur: ['gray', Validators.required],
    actif:   [true],
  });

  loadStatutsVehicule(): void {
    this.statutsVehiculeLoad.set(true);
    this.parametrageApi.getStatutsVehicule().subscribe({
      next: (l) => { this.statutsVehicule.set(l); this.statutsVehiculeLoad.set(false); },
      error: () => this.statutsVehiculeLoad.set(false),
    });
  }

  ouvrirNouveauStatutVehicule(): void {
    this.editStatutVehiculeId.set(null);
    this.statutsVehiculeError.set('');
    this.statutVehiculeForm.reset({ couleur: 'gray', actif: true });
    this.showStatutVehiculeModal.set(true);
  }

  editStatutVehicule(s: any): void {
    this.editStatutVehiculeId.set(s.id);
    this.statutsVehiculeError.set('');
    this.statutVehiculeForm.patchValue({ code: s.code, libelle: s.libelle, couleur: s.couleur, actif: s.actif });
    this.showStatutVehiculeModal.set(true);
  }

  cancelEditStatutVehicule(): void {
    this.editStatutVehiculeId.set(null);
    this.showStatutVehiculeModal.set(false);
    this.statutVehiculeForm.reset({ couleur: 'gray', actif: true });
    this.statutsVehiculeError.set('');
  }

  saveStatutVehicule(): void {
    if (this.statutVehiculeForm.invalid) return;
    const id  = this.editStatutVehiculeId();
    const req = id
      ? this.parametrageApi.updateStatutVehicule(id, this.statutVehiculeForm.value)
      : this.parametrageApi.createStatutVehicule(this.statutVehiculeForm.value);
    req.subscribe({
      next: () => {
        this.statutsVehiculeSuccess.set(id ? 'Statut modifié.' : 'Statut créé.');
        this.cancelEditStatutVehicule();
        this.loadStatutsVehicule();
        setTimeout(() => this.statutsVehiculeSuccess.set(''), 3000);
      },
      error: (err: any) => this.statutsVehiculeError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  demanderSuppressionStatutVehicule(s: any): void { this.deleteStatutVehiculeConfirm.set(s); }
  annulerSuppressionStatutVehicule(): void         { this.deleteStatutVehiculeConfirm.set(null); }

  confirmerSuppressionStatutVehicule(): void {
    const s = this.deleteStatutVehiculeConfirm();
    if (!s) return;
    this.parametrageApi.deleteStatutVehicule(s.id).subscribe({
      next: () => { this.deleteStatutVehiculeConfirm.set(null); this.loadStatutsVehicule(); },
      error: (err: any) => {
        this.erreurSuppression(err);
        this.deleteStatutVehiculeConfirm.set(null);
      },
    });
  }

  // ── Marques véhicule ─────────────────────────────────────────────
  marques           = signal<any[]>([]);
  marquesLoad       = signal(false);
  marquesError      = signal('');
  marquesSuccess    = signal('');
  editMarqueId      = signal<number | null>(null);
  showMarqueModal   = signal(false);
  deleteMarqueConfirm = signal<any>(null);

  marqueForm = this.fb.group({
    libelle: ['', Validators.required],
    actif:   [true],
  });

  loadMarques(): void {
    this.marquesLoad.set(true);
    this.parametrageApi.getMarques().subscribe({
      next: (l) => { this.marques.set(l); this.marquesLoad.set(false); },
      error: () => this.marquesLoad.set(false),
    });
  }

  ouvrirNouvelleMarque(): void {
    this.editMarqueId.set(null);
    this.marquesError.set('');
    this.marqueForm.reset({ actif: true });
    this.showMarqueModal.set(true);
  }

  editMarque(m: any): void {
    this.editMarqueId.set(m.id);
    this.marquesError.set('');
    this.marqueForm.patchValue({ libelle: m.libelle, actif: m.actif });
    this.showMarqueModal.set(true);
  }

  cancelEditMarque(): void {
    this.editMarqueId.set(null);
    this.showMarqueModal.set(false);
    this.marqueForm.reset({ actif: true });
    this.marquesError.set('');
  }

  saveMarque(): void {
    if (this.marqueForm.invalid) return;
    const id  = this.editMarqueId();
    const req = id
      ? this.parametrageApi.updateMarque(id, this.marqueForm.value)
      : this.parametrageApi.createMarque(this.marqueForm.value);
    req.subscribe({
      next: () => {
        this.marquesSuccess.set(id ? 'Marque modifiée.' : 'Marque créée.');
        this.cancelEditMarque();
        this.loadMarques();
        this.loadModeles();
        setTimeout(() => this.marquesSuccess.set(''), 3000);
      },
      error: (err: any) => this.marquesError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  demanderSuppressionMarque(m: any): void { this.deleteMarqueConfirm.set(m); }
  annulerSuppressionMarque(): void         { this.deleteMarqueConfirm.set(null); }

  confirmerSuppressionMarque(): void {
    const m = this.deleteMarqueConfirm();
    if (!m) return;
    this.parametrageApi.deleteMarque(m.id).subscribe({
      next: () => { this.deleteMarqueConfirm.set(null); this.loadMarques(); this.loadModeles(); },
      error: (err: any) => {
        this.erreurSuppression(err);
        this.deleteMarqueConfirm.set(null);
      },
    });
  }

  // Marque sélectionnée dans la vue maître / détail
  marqueSelectionneeId = signal<number | null>(null);
  marqueSelectionnee = computed(() => {
    const id = this.marqueSelectionneeId();
    return this.marques().find(m => m.id === id) ?? this.marques()[0] ?? null;
  });
  modelesMarque = computed(() => {
    const m = this.marqueSelectionnee();
    return m ? this.modeles().filter(x => x.marque === m.id) : [];
  });

  // ── Modèles véhicule ─────────────────────────────────────────────
  modeles           = signal<any[]>([]);
  modelesLoad       = signal(false);
  modelesError      = signal('');
  modelesSuccess    = signal('');
  editModeleId      = signal<number | null>(null);
  showModeleModal   = signal(false);
  deleteModeleConfirm = signal<any>(null);

  modeleForm = this.fb.group({
    marque:  [null as number | null, Validators.required],
    libelle: ['', Validators.required],
    actif:   [true],
  });

  loadModeles(): void {
    this.modelesLoad.set(true);
    this.parametrageApi.getModeles().subscribe({
      next: (l) => { this.modeles.set(l); this.modelesLoad.set(false); },
      error: () => this.modelesLoad.set(false),
    });
  }

  ouvrirNouveauModele(): void {
    this.editModeleId.set(null);
    this.modelesError.set('');
    this.modeleForm.reset({ actif: true, marque: this.marqueSelectionnee()?.id ?? null });
    this.showModeleModal.set(true);
  }

  editModele(m: any): void {
    this.editModeleId.set(m.id);
    this.modelesError.set('');
    this.modeleForm.patchValue({ marque: m.marque, libelle: m.libelle, actif: m.actif });
    this.showModeleModal.set(true);
  }

  cancelEditModele(): void {
    this.editModeleId.set(null);
    this.showModeleModal.set(false);
    this.modeleForm.reset({ actif: true, marque: null });
    this.modelesError.set('');
  }

  saveModele(): void {
    if (this.modeleForm.invalid) return;
    const id  = this.editModeleId();
    const req = id
      ? this.parametrageApi.updateModele(id, this.modeleForm.value)
      : this.parametrageApi.createModele(this.modeleForm.value);
    req.subscribe({
      next: () => {
        this.modelesSuccess.set(id ? 'Modèle modifié.' : 'Modèle créé.');
        this.cancelEditModele();
        this.loadModeles();
        this.loadMarques();
        setTimeout(() => this.modelesSuccess.set(''), 3000);
      },
      error: (err: any) => this.modelesError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  demanderSuppressionModele(m: any): void { this.deleteModeleConfirm.set(m); }
  annulerSuppressionModele(): void         { this.deleteModeleConfirm.set(null); }

  confirmerSuppressionModele(): void {
    const m = this.deleteModeleConfirm();
    if (!m) return;
    this.parametrageApi.deleteModele(m.id).subscribe({
      next: () => { this.deleteModeleConfirm.set(null); this.loadModeles(); this.loadMarques(); },
      error: (err: any) => {
        this.erreurSuppression(err);
        this.deleteModeleConfirm.set(null);
      },
    });
  }

  // ── Import Excel des tournées ────────────────────────────────────
  showImportModal   = signal(false);
  importFichier     = signal<File | null>(null);
  importLoading     = signal(false);
  importError       = signal('');
  importResultat    = signal<any>(null);

  ouvrirImportTournees(): void {
    this.importFichier.set(null);
    this.importError.set('');
    this.importResultat.set(null);
    this.importLoading.set(false);
    this.showImportModal.set(true);
  }

  fermerImportTournees(): void {
    this.showImportModal.set(false);
    this.importLoading.set(false);
  }

  onImportFichierChange(e: Event): void {
    const f = (e.target as HTMLInputElement).files?.[0] ?? null;
    this.importFichier.set(f);
    this.importError.set('');
    this.importResultat.set(null);
  }

  lancerImportTournees(): void {
    const f = this.importFichier();
    if (!f || this.importLoading()) return;
    this.importLoading.set(true);
    this.importError.set('');
    this.importResultat.set(null);
    this.parametrageApi.importTourneesExcel(f).subscribe({
      next: (res: any) => {
        this.importLoading.set(false);
        this.importResultat.set(res);
        this.loadTournees();
      },
      error: (err: any) => {
        this.importLoading.set(false);
        this.importError.set(err?.error?.detail ?? "Erreur lors de l'import.");
      },
    });
  }

  // Modèle de fichier CSV à remplir
  telechargerModeleTournees(): void {
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['code', 'libelle', 'agence', 'dotation', 'km_theorique', 'actif'].join(sep);
    const exemples = [
      ['NORD1', "NORD1-KORHOGO-TENGRELA-M'BENGUE", this.agences()[0]?.code ?? 'ABJ', '100', '870', 'oui'],
      ['BKE2',  'BOUAKE 2-DABAKALA',               this.agences()[0]?.code ?? 'ABJ', '30',  '261', 'oui'],
    ].map(l => l.join(sep)).join(eol);
    const csv = '\uFEFF' + hdrs + eol + exemples;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'modele_import_tournees.csv';
    a.click(); URL.revokeObjectURL(a.href);
  }

  // ── Exports CSV ──────────────────────────────────────────────────
  /** Génère et télécharge un fichier CSV (séparateur ';', BOM UTF-8 pour Excel). */
  private exporterCsv(nomFichier: string, entetes: string[], lignes: (string | number)[][]): void {
    if (!lignes.length) return;
    const sep = ';'; const eol = '\r\n';
    const echapper = (v: string | number): string => {
      const s = String(v ?? '');
      // Neutraliser les caractères qui casseraient la structure du CSV
      return s.replace(/[\r\n]+/g, ' ').replace(/;/g, ',');
    };
    const contenu = '\uFEFF'
      + entetes.join(sep) + eol
      + lignes.map(l => l.map(echapper).join(sep)).join(eol);
    const blob = new Blob([contenu], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${nomFichier}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  private ouiNon(v: boolean): string { return v ? 'Oui' : 'Non'; }

  exportTypes(): void {
    this.exporterCsv('types_intervention',
      ['Nom', 'Catégorie', 'Périodicité (km)', 'Périodicité (mois)'],
      this.types().map((t: any) => [
        t.nom, t.categorie_display ?? t.categorie ?? '',
        t.periodicite_km ?? '', t.periodicite_mois ?? '',
      ]));
  }

  exportTypesDoc(): void {
    this.exporterCsv('types_document',
      ['Ordre', 'Code', 'Libellé', 'Nb documents', 'Actif'],
      this.typesDoc().map((t: any) => [
        t.ordre ?? '', t.code, t.libelle, t.nb_documents ?? 0, this.ouiNon(t.actif),
      ]));
  }

  exportPrestataires(): void {
    this.exporterCsv('prestataires',
      ['Nom', 'Spécialité', 'Ville', 'Téléphone', 'Email', 'Adresse', 'Note qualité'],
      this.prestataires().map((p: any) => [
        p.nom, p.specialite ?? '', p.ville ?? '', p.telephone ?? '',
        p.email ?? '', p.adresse ?? '', p.note_qualite ?? '',
      ]));
  }

  exportAssureurs(): void {
    this.exporterCsv('assureurs',
      ['Nom', 'Téléphone', 'Email', 'Contact sinistre', 'Adresse', 'Actif'],
      this.assureurs().map((a: any) => [
        a.nom, a.telephone ?? '', a.email ?? '',
        a.contact_sinistre ?? '', a.adresse ?? '', this.ouiNon(a.is_active),
      ]));
  }

  exportAgences(): void {
    this.exporterCsv('agences',
      ['Code', 'Nom', 'Ville', 'Téléphone', 'Responsable', 'Nb véhicules', 'Adresse', 'Actif'],
      this.agences().map((a: any) => [
        a.code, a.nom, a.ville ?? '', a.telephone ?? '',
        a.responsable_nom ?? '', a.nb_vehicules ?? 0,
        a.adresse ?? '', this.ouiNon(a.is_active),
      ]));
  }

  exportTournees(): void {
    this.exporterCsv('tournees',
      ['code', 'libelle', 'agence', 'dotation', 'km_theorique', 'actif'],
      this.tourneesFiltrees().map((t: any) => [
        t.code, t.libelle, t.agence_code ?? t.agence_nom ?? '',
        t.dotation ?? 0, t.km_theorique ?? 0, this.ouiNon(t.actif),
      ]));
  }

  exportAffectations(): void {
    this.exporterCsv('affectations_usage',
      ['Code', 'Libellé', 'Actif'],
      this.affectations().map((a: any) => [
        a.code, a.libelle, this.ouiNon(a.actif),
      ]));
  }

  exportStatuts(): void {
    this.exporterCsv('statuts_vehicule',
      ['Code', 'Libellé', 'Couleur', 'Actif'],
      this.statutsVehicule().map((s: any) => [
        s.code, s.libelle, s.couleur ?? '', this.ouiNon(s.actif),
      ]));
  }

  exportMarques(): void {
    this.exporterCsv('marques_vehicule',
      ['Libellé', 'Nb modèles', 'Actif'],
      this.marques().map((m: any) => [
        m.libelle, m.nb_modeles ?? 0, this.ouiNon(m.actif),
      ]));
  }

  exportModeles(): void {
    this.exporterCsv('modeles_vehicule',
      ['Marque', 'Libellé', 'Actif'],
      this.modeles().map((m: any) => [
        m.marque_libelle ?? '', m.libelle, this.ouiNon(m.actif),
      ]));
  }

  // ── Stations ─────────────────────────────────────────────────────
  stations          = signal<any[]>([]);
  stationEditee     = signal<any | null | undefined>(undefined);   // undefined = fermée, null = création
  stationErreur     = signal('');
  stationForm = this.fb.group({
    nom:            ['', Validators.required],
    ville:          [''],
    adresse:        [''],
    agence:         [null as string | null],
    est_partenaire: [false],
    is_active:      [true],
  });
  /** Une station commune (sans agence) n'est possible que pour un utilisateur « Toutes les agences ». */
  peutCreerStationCommune = computed(() => !this.auth.currentUser()?.agence);

  loadStations(): void {
    this.carburantApi.getStations({ tous: 1, page_size: 500 }).subscribe({
      next: (res: any) => this.stations.set(Array.isArray(res) ? res : (res.results ?? [])),
      error: () => this.stations.set([]),
    });
  }

  ouvrirStation(st: any | null): void {
    this.stationErreur.set('');
    this.stationForm.reset(st
      ? { nom: st.nom, ville: st.ville, adresse: st.adresse, agence: st.agence, est_partenaire: st.est_partenaire, is_active: st.is_active }
      : { nom: '', ville: '', adresse: '', agence: null, est_partenaire: false, is_active: true });
    this.stationEditee.set(st);
  }

  enregistrerStation(): void {
    if (this.stationForm.invalid) return;
    const st = this.stationEditee();
    const req = st ? this.carburantApi.updateStation(st.id, this.stationForm.value)
                   : this.carburantApi.createStation(this.stationForm.value);
    req.subscribe({
      next: () => { this.stationEditee.set(undefined); this.notice.set({ type: 'ok', texte: st ? 'Station modifiée.' : 'Station créée.' }); this.loadStations(); },
      error: (err: any) => this.stationErreur.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  basculerStation(x: any): void { this.basculer(this.carburantApi.updateStation(x.id, { is_active: !x.is_active }), () => this.loadStations()); }

  supprimerStation(x: any): void {
    if (!confirm(`Supprimer la station « ${x.nom} » ?`)) return;
    this.carburantApi.deleteStation(x.id).subscribe({ next: () => this.loadStations(), error: (err) => this.erreurSuppression(err) });
  }

  exportStations(): void {
    this.exporterCsv('stations',
      ['Nom', 'Ville', 'Agence', 'Partenaire', 'Prises de carburant', 'Active'],
      this.stations().map((x: any) => [x.nom, x.ville ?? '', x.agence_nom ?? 'Toutes', this.ouiNon(x.est_partenaire),
                                        x.nb_utilisations ?? 0, this.ouiNon(x.is_active)]));
  }

  // ── Types de mouvement ───────────────────────────────────────────
  typesMouvement      = signal<any[]>([]);
  typeMvtEdite        = signal<any | null | undefined>(undefined);
  typeMvtErreur       = signal('');
  readonly couleursTypeMvt = [
    { value: 'gray', label: 'Gris' }, { value: 'green', label: 'Vert' }, { value: 'orange', label: 'Orange' },
    { value: 'blue', label: 'Bleu' }, { value: 'red', label: 'Rouge' },
  ];
  typeMvtForm = this.fb.group({
    code:         ['', [Validators.required, Validators.pattern(/^[a-z0-9_-]+$/)]],
    libelle:      ['', Validators.required],
    couleur:      ['gray'],
    ordre:        [0],
    actif:        [true],
    pour_releves: [true],
    pour_prises:  [false],
  });

  loadTypesMouvement(): void {
    this.parametrageApi.getTypesMouvement().subscribe({
      next: l => { this.typesMouvement.set(l); this.typesMvtCache.charger(true); },
      error: () => this.typesMouvement.set([]),
    });
  }

  ouvrirTypeMvt(t: any | null): void {
    this.typeMvtErreur.set('');
    this.typeMvtForm.reset(t
      ? { code: t.code, libelle: t.libelle, couleur: t.couleur, ordre: t.ordre, actif: t.actif,
          pour_releves: t.pour_releves, pour_prises: t.pour_prises }
      : { code: '', libelle: '', couleur: 'gray', ordre: this.typesMouvement().length + 1, actif: true,
          pour_releves: false, pour_prises: true });
    if (t) this.typeMvtForm.controls.code.disable(); else this.typeMvtForm.controls.code.enable();
    // Type réservé « Tournée » : toujours proposé dans les deux saisies
    for (const c of [this.typeMvtForm.controls.pour_releves, this.typeMvtForm.controls.pour_prises]) {
      if (t?.reserve) c.disable(); else c.enable();
    }
    this.typeMvtEdite.set(t);
  }

  enregistrerTypeMvt(): void {
    if (this.typeMvtForm.invalid) return;
    const t = this.typeMvtEdite();
    const req = t ? this.parametrageApi.updateTypeMouvement(t.id, this.typeMvtForm.value)
                  : this.parametrageApi.createTypeMouvement(this.typeMvtForm.value);
    req.subscribe({
      next: () => { this.typeMvtEdite.set(undefined); this.notice.set({ type: 'ok', texte: t ? 'Type modifié.' : 'Type créé.' }); this.loadTypesMouvement(); },
      error: (err: any) => this.typeMvtErreur.set(
        err?.error?.detail ?? err?.error?.code?.[0] ?? err?.error?.non_field_errors?.[0]
          ?? "Erreur lors de l'enregistrement."),
    });
  }

  /** Saisie (relevés / prises) d'un type cochée ou décochée depuis le tableau. */
  basculerSaisieTypeMvt(x: any, champ: 'pour_releves' | 'pour_prises'): void {
    this.parametrageApi.updateTypeMouvement(x.id, { [champ]: !x[champ] }).subscribe({
      next: () => this.loadTypesMouvement(),
      error: (err: any) => this.notice.set({ type: 'err', texte: err?.error?.non_field_errors?.[0]
        ?? err?.error?.detail ?? 'Modification impossible.' }),
    });
  }

  basculerTypeMvt(x: any): void { this.basculer(this.parametrageApi.updateTypeMouvement(x.id, { actif: !x.actif }), () => this.loadTypesMouvement()); }

  supprimerTypeMvt(x: any): void {
    if (!confirm(`Supprimer le type « ${x.libelle} » ?`)) return;
    this.parametrageApi.deleteTypeMouvement(x.id).subscribe({ next: () => this.loadTypesMouvement(), error: (err) => this.erreurSuppression(err) });
  }

  // ── Dotation des tournées (demande soumise au circuit de validation) ──
  tourneeDotation    = signal<any | null>(null);
  historiqueDotation = signal<any[]>([]);
  dotationErreur     = signal('');
  dotationEnvoi      = signal(false);
  dotationForm = this.fb.group({
    nouvelle_dotation: [null as number | null, [Validators.required, Validators.min(0)]],
    motif:             ['', Validators.required],
  });

  ouvrirDotation(t: any): void {
    this.dotationErreur.set('');
    this.dotationForm.reset({ nouvelle_dotation: null, motif: '' });
    this.tourneeDotation.set(t);
    this.historiqueDotation.set([]);
    this.parametrageApi.historiqueDotation(t.id).subscribe({
      next: h => this.historiqueDotation.set(h),
      error: () => this.dotationErreur.set("Impossible de charger l'historique."),
    });
  }

  demanderDotation(): void {
    const t = this.tourneeDotation();
    if (!t || this.dotationForm.invalid || this.dotationEnvoi()) return;
    this.dotationEnvoi.set(true);
    this.parametrageApi.demanderDotation(t.id, this.dotationForm.value as any).subscribe({
      next: () => {
        this.dotationEnvoi.set(false);
        this.tourneeDotation.set(null);
        this.notice.set({ type: 'ok', texte: `Demande envoyée : la dotation de ${t.code} sera mise à jour après validation (suivi dans Demandes).` });
        this.loadTournees();
      },
      error: (err: any) => {
        this.dotationEnvoi.set(false);
        const e = err?.error ?? {};
        this.dotationErreur.set(e.detail ?? e.nouvelle_dotation ?? e.motif ?? "Erreur lors de l'envoi de la demande.");
      },
    });
  }

  statutDotationClasse(statut: string): string {
    return ({ initiale: 'badge-gray', en_attente: 'badge-warning', approuvee: 'badge-green',
              rejetee: 'badge-danger', annulee: 'badge-gray' } as Record<string, string>)[statut] ?? 'badge-gray';
  }
}
