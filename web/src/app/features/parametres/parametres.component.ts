// UbiFleet — Paramètres Component (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { EntretienApiService, ParametrageApiService, SinistreApiService, AgenceApiService, VehiculeApiService } from '../../core/services/api.service';
import { Prestataire, Assureur, Agence } from '../../core/models';

@Component({
  selector: 'ubi-parametres',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe],
  templateUrl: './parametres.component.html',
  styleUrls: ['./parametres.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ParametresComponent implements OnInit {
  private fb             = inject(FormBuilder);
  private entretienApi   = inject(EntretienApiService);
  private parametrageApi = inject(ParametrageApiService);
  private sinistreApi    = inject(SinistreApiService);
  private vehiculeApi    = inject(VehiculeApiService);
  private agenceApi      = inject(AgenceApiService);

  activeTab = signal<'alertes' | 'types' | 'types_doc' | 'prestataires' | 'assureurs' | 'agences' | 'tournees' | 'affectations' | 'statuts' | 'marques' | 'modeles'>('alertes');

  // ── Alertes paramètres ──
  parametres = signal<any[]>([]);
  paramSaving = signal(false);
  paramSuccess = signal('');
  paramError   = signal('');

  alertesForm = this.fb.group({
    alerte_permis_jours:         [60,  [Validators.required, Validators.min(1)]],
    alerte_assurance_jours:      [30,  [Validators.required, Validators.min(1)]],
    alerte_ct_jours:             [30,  [Validators.required, Validators.min(1)]],
    alerte_conso_seuil_pct:      [30,  [Validators.required, Validators.min(1)]],
    etat_parc_km_urgent:         [500, [Validators.required, Validators.min(1)]],
    etat_parc_km_attention:      [2000,[Validators.required, Validators.min(1)]],
    etat_parc_jours_urgent:      [7,   [Validators.required, Validators.min(1)]],
    etat_parc_jours_attention:   [30,  [Validators.required, Validators.min(1)]],
    prix_carburant_litre:        [700, [Validators.required, Validators.min(1)]],
  });

  get af() { return this.alertesForm.controls; }

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
    this.loadParametres();
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
  }

  // ── Paramètres ──
  loadParametres(): void {
    this.parametrageApi.getAll('alertes').subscribe({
      next: (list) => {
        this.parametres.set(list);
        const vals: Record<string, any> = {};
        list.forEach((p: any) => vals[p.cle] = p.valeur_typee);
        this.alertesForm.patchValue(vals);
      },
      error: () => {},
    });
  }

  saveParametres(): void {
    if (this.alertesForm.invalid || this.paramSaving()) return;
    this.paramSaving.set(true);
    this.paramSuccess.set('');
    this.paramError.set('');

    const items = Object.entries(this.alertesForm.value).map(([cle, valeur]) => ({
      cle, valeur: String(valeur)
    }));

    this.parametrageApi.bulkUpdate(items).subscribe({
      next: () => {
        this.paramSaving.set(false);
        this.paramSuccess.set('Paramètres enregistrés avec succès.');
        this.loadParametres();  // Recharger depuis la base pour afficher les vraies valeurs
      },
      error: () => {
        this.paramSaving.set(false);
        this.paramError.set('Erreur lors de l\'enregistrement.');
      },
    });
  }

  // ── Types ──
  loadTypes(): void {
    this.entretienApi.getTypes().subscribe({
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
      error: () => {},
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
      error: () => {},
    });
  }

  // ── Assureurs ──
  loadAssureurs(): void {
    this.assureursLoad.set(true);
    this.sinistreApi.getAssureurs().subscribe({
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
      error: () => {},
    });
  }

  // ── Prestataires ──
  loadPrestataires(): void {
    this.entretienApi.getPrestataires({ page_size: 100 }).subscribe({
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
      error: () => {},
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
    this.showTourneeModal.set(true);
  }

  editTournee(t: any): void {
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
        this.tourneesError.set(err?.error?.detail ?? 'Impossible de supprimer.');
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
    this.loadMarques();
    this.loadModeles();
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
        this.affectationsError.set(err?.error?.detail ?? 'Impossible de supprimer.');
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
        this.statutsVehiculeError.set(err?.error?.detail ?? 'Impossible de supprimer.');
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
        this.marquesError.set(err?.error?.detail ?? 'Impossible de supprimer (des véhicules ou modèles y sont liés).');
        this.deleteMarqueConfirm.set(null);
      },
    });
  }

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
    this.modeleForm.reset({ actif: true, marque: null });
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
        this.modelesError.set(err?.error?.detail ?? 'Impossible de supprimer (des véhicules y sont liés).');
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

  exportParametres(): void {
    this.exporterCsv('parametres_alertes',
      ['Clé', 'Libellé', 'Valeur', 'Catégorie'],
      this.parametres().map((p: any) => [
        p.cle, p.description ?? '', p.valeur, p.categorie ?? '',
      ]));
  }

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
}
