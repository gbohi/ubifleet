// UbiFleet — Vehicule Detail Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DecimalPipe, DatePipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { VehiculesStore } from '../../../store/vehicules/vehicules.store';
import {
  VehiculeApiService,
  EntretienApiService,
  CarburantApiService,
  SinistreApiService,
  ChauffeurApiService,
  ParametrageApiService
} from '../../../core/services/api.service';
import {
  Intervention, PleinCarburant, DocumentVehicule,
  StatutIntervention, ContratAssurance, HistoriqueImmatriculation,
  ReleveKilometrage, AffectationVehicule
} from '../../../core/models';

type TabType = 'infos' | 'carburant' | 'entretiens' | 'assurance' | 'documents' | 'historique-km' | 'chauffeurs' | 'statut';

@Component({
  selector: 'ubi-vehicule-detail',
  standalone: true,
  imports: [RouterLink, DecimalPipe, DatePipe, ReactiveFormsModule],
  templateUrl: './vehicule-detail.component.html',
  styleUrls: ['./vehicule-detail.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculeDetailComponent implements OnInit {
  id = input.required<string>();

  store         = inject(VehiculesStore);
  router                = inject(Router);
  private fb            = inject(FormBuilder);
  private vehiculeApi    = inject(VehiculeApiService);
  private parametrageApi = inject(ParametrageApiService);
  private entretienApi  = inject(EntretienApiService);
  private carburantApi  = inject(CarburantApiService);
  private sinistreApi   = inject(SinistreApiService);
  private chauffeurApi  = inject(ChauffeurApiService);

  activeTab = signal<TabType>('infos');

  // ── Onglet Assurance ──
  contrats      = signal<ContratAssurance[]>([]);
  contratsLoad  = signal(false);

  // ── Onglet Entretiens ──
  interventions      = signal<Intervention[]>([]);
  interventionsTotal = signal(0);
  interventionsLoad  = signal(false);

  // ── Onglet Carburant ──
  pleins      = signal<PleinCarburant[]>([]);
  pleinsTotal = signal(0);
  pleinsLoad  = signal(false);

  // ── Onglet Documents ──
  showUploadModal  = signal(false);
  showEditDocModal = signal<DocumentVehicule | null>(null);
  uploadLoading    = signal(false);
  uploadError      = signal('');
  uploadSuccess    = signal('');
  selectedFile     = signal<File | null>(null);
  editSelectedFile = signal<File | null>(null);
  deleteDocConfirm = signal<string | null>(null);

  uploadForm = this.fb.group({
    type_document:   ['carte_grise', Validators.required],
    numero:          [''],
    date_emission:   [''],
    date_expiration: [''],
    notes:           [''],
  });

  editDocForm = this.fb.group({
    type_document:   ['', Validators.required],
    numero:          [''],
    date_emission:   [''],
    date_expiration: [''],
    notes:           [''],
  });

  get uf() { return this.uploadForm.controls; }
  get ef() { return this.editDocForm.controls; }

  typesDocument = signal<{ id: number; code: string; libelle: string }[]>([]);

  // ── Données chauffeurs pour les modaux ──
  chauffeurs = signal<{ id: string; nom_complet: string }[]>([]);

  // ── Modal changement immatriculation ──
  showImmatModal    = signal(false);
  newImmat          = signal('');
  dateImmat         = signal(new Date().toISOString().split('T')[0]);
  motifImmat        = signal('Passage de provisoire à définitive');
  immatLoading      = signal(false);
  immatError        = signal('');
  immatSuccess      = signal('');
  historiqueImmat   = signal<HistoriqueImmatriculation[]>([]);

  // ── Modal kilométrage ──
  showKmModal     = signal(false);
  kmValue         = signal<number>(0);
  kmDate          = signal(new Date().toISOString().split('T')[0]);
  kmTypeMouvement = signal<'entree' | 'sortie' | 'releve' | 'tournee'>('releve');
  kmChauffeur     = signal('');
  kmTournee       = signal('');
  kmNotes         = signal('');
  kmLoading       = signal(false);
  kmError         = signal('');
  kmPhoto         = signal<File | null>(null);
  kmPhotoPreview  = signal<string | null>(null);
  photoLightbox   = signal<string | null>(null);

  ngOnInit(): void {
    this.store.loadVehiculeDetail(this.id());
    this.vehiculeApi.getTypesDocument(true).subscribe({
      next: (list) => this.typesDocument.set(list ?? []),
      error: () => {},
    });
    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res) => this.chauffeurs.set(
        (res.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });
  }

  onTabChange(tab: TabType): void {
    this.activeTab.set(tab);
    if (tab === 'entretiens' && this.interventions().length === 0) {
      this.loadInterventions();
    }
    if (tab === 'carburant' && this.pleins().length === 0) {
      this.loadPleins();
    }
    if (tab === 'assurance' && this.contrats().length === 0) {
      this.loadContrats();
    }
    if (tab === 'historique-km') {
      this.loadRelevesKm();
    }
    if (tab === 'chauffeurs') {
      this.loadAffectations();
    }
  }

  // ── Entretiens du véhicule ──
  loadInterventions(): void {
    this.interventionsLoad.set(true);
    this.entretienApi.getByVehicule(this.id(), { page_size: 10 }).subscribe({
      next: (res) => {
        this.interventions.set(res.results ?? []);
        this.interventionsTotal.set(res.count ?? 0);
        this.interventionsLoad.set(false);
      },
      error: () => this.interventionsLoad.set(false),
    });
  }

  goToIntervention(id: string): void {
    this.router.navigate(['/entretien', id]);
  }

  planifierIntervention(): void {
    this.router.navigate(['/entretien', 'nouveau'], {
      queryParams: { vehicule: this.id() }
    });
  }

  // ── Onglet Chauffeurs (affectations) ──
  affectations      = signal<AffectationVehicule[]>([]);
  affectationsLoad  = signal(false);
  showAffectForm    = signal(false);
  editAffectId      = signal<string | null>(null);
  affectSaving      = signal(false);
  affectError       = signal('');
  affectSuccess     = signal('');
  deleteAffectId    = signal<string | null>(null);

  affectForm = this.fb.group({
    chauffeur:  ['', Validators.required],
    date_debut: [new Date().toISOString().split('T')[0], Validators.required],
    date_fin:   [''],
    notes:      [''],
  });

  get aff() { return this.affectForm.controls; }

  // ── Méthodes affectations ──
  loadAffectations(): void {
    this.affectationsLoad.set(true);
    this.vehiculeApi.getAffectations({ vehicule: this.id() }).subscribe({
      next: (res) => {
        this.affectations.set(res.results ?? []);
        this.affectationsLoad.set(false);
      },
      error: () => this.affectationsLoad.set(false),
    });
  }

  openAffectForm(a?: AffectationVehicule): void {
    this.affectError.set('');
    this.affectSuccess.set('');
    if (a) {
      this.editAffectId.set(a.id);
      this.affectForm.patchValue({
        chauffeur:  a.chauffeur,
        date_debut: a.date_debut,
        date_fin:   a.date_fin ?? '',
        notes:      a.notes,
      });
    } else {
      this.editAffectId.set(null);
      this.affectForm.reset({
        date_debut: new Date().toISOString().split('T')[0],
      });
    }
    this.showAffectForm.set(true);
  }

  closeAffectForm(): void { this.showAffectForm.set(false); }

  saveAffectation(): void {
    if (this.affectForm.invalid || this.affectSaving()) return;
    this.affectSaving.set(true);
    this.affectError.set('');

    const raw = this.affectForm.value;
    const payload: Record<string, any> = {
      vehicule:   this.id(),
      chauffeur:  raw.chauffeur,
      date_debut: raw.date_debut,
    };
    if (raw.date_fin)  payload['date_fin'] = raw.date_fin;
    if (raw.notes)     payload['notes']    = raw.notes;

    const req = this.editAffectId()
      ? this.vehiculeApi.updateAffectation(this.editAffectId()!, payload)
      : this.vehiculeApi.createAffectation(payload as any);

    req.subscribe({
      next: () => {
        this.affectSaving.set(false);
        this.affectSuccess.set(this.editAffectId() ? 'Affectation modifiée.' : 'Affectation créée.');
        this.closeAffectForm();
        this.loadAffectations();
      },
      error: (err) => {
        this.affectSaving.set(false);
        this.affectError.set(err?.error?.detail ?? "Erreur lors de l'enregistrement.");
      },
    });
  }

  confirmDeleteAffect(id: string): void { this.deleteAffectId.set(id); }
  cancelDeleteAffect(): void            { this.deleteAffectId.set(null); }

  doDeleteAffect(id: string): void {
    this.vehiculeApi.deleteAffectation(id).subscribe({
      next: () => { this.deleteAffectId.set(null); this.loadAffectations(); },
      error: () => this.deleteAffectId.set(null),
    });
  }

  // ── Historique kilométrage dans l'onglet ──
  relevesKm      = signal<ReleveKilometrage[]>([]);
  relevesKmTotal = signal(0);
  relevesKmLoad  = signal(false);

  loadRelevesKm(): void {
    this.relevesKmLoad.set(true);
    this.vehiculeApi.getRelevesKm({ vehicule: this.id(), page_size: 20 }).subscribe({
      next: (res) => {
        this.relevesKm.set(res.results ?? []);
        this.relevesKmTotal.set(res.count ?? 0);
        this.relevesKmLoad.set(false);
      },
      error: () => this.relevesKmLoad.set(false),
    });
  }

  // ── Assurance du véhicule ──
  loadContrats(): void {
    this.contratsLoad.set(true);
    this.sinistreApi.getContratsByVehicule(this.id()).subscribe({
      next: (res) => {
        this.contrats.set(res.results ?? []);
        this.contratsLoad.set(false);
      },
      error: () => this.contratsLoad.set(false),
    });
  }

  goToContrats(): void {
    this.router.navigate(['/sinistres'], { queryParams: { tab: 'contrats', vehicule: this.id() } });
  }

  joursContratClass(jours: number): string {
    if (jours <= 0)  return 'badge-danger';
    if (jours <= 30) return 'badge-danger';
    if (jours <= 60) return 'badge-warning';
    return 'badge-green';
  }

  // ── Carburant du véhicule ──
  loadPleins(): void {
    this.pleinsLoad.set(true);
    this.carburantApi.getPleinsVehicule(this.id(), { page_size: 10 }).subscribe({
      next: (res) => {
        this.pleins.set(res.results ?? []);
        this.pleinsTotal.set(res.count ?? 0);
        this.pleinsLoad.set(false);
      },
      error: () => this.pleinsLoad.set(false),
    });
  }

  // ── Documents ──
  openUpload(): void {
    this.uploadError.set('');
    this.uploadSuccess.set('');
    this.selectedFile.set(null);
    this.uploadForm.reset({ type_document: this.typesDocument()[0]?.id?.toString() ?? '' });
    this.showUploadModal.set(true);
  }

  closeUpload(): void {
    this.showUploadModal.set(false);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.selectedFile.set(input.files[0]);
    }
  }

  submitUpload(): void {
    if (!this.selectedFile() || this.uploadForm.invalid || this.uploadLoading()) return;
    this.uploadLoading.set(true);
    this.uploadError.set('');

    const formData = new FormData();
    const vals = this.uploadForm.value;
    formData.append('fichier', this.selectedFile()!);
    formData.append('vehicule', this.id());
    formData.append('type_document', vals.type_document ?? '');
    if (vals.numero)          formData.append('numero', vals.numero);
    if (vals.date_emission)   formData.append('date_emission', vals.date_emission);
    if (vals.date_expiration) formData.append('date_expiration', vals.date_expiration);
    if (vals.notes)           formData.append('notes', vals.notes);

    this.vehiculeApi.uploadDocument(this.id(), formData).subscribe({
      next: () => {
        this.uploadLoading.set(false);
        this.uploadSuccess.set('Document ajouté avec succès.');
        this.closeUpload();
        this.store.loadVehiculeDetail(this.id());
      },
      error: (err) => {
        this.uploadLoading.set(false);
        this.uploadError.set(err?.error?.detail ?? "Erreur lors de l'upload.");
      },
    });
  }

  openEditDoc(doc: DocumentVehicule): void {
    this.showEditDocModal.set(doc);
    this.editSelectedFile.set(null);
    this.editDocForm.patchValue({
      type_document:   doc.type_document,
      numero:          doc.numero ?? '',
      date_emission:   doc.date_emission ?? '',
      date_expiration: doc.date_expiration ?? '',
      notes:           doc.notes ?? '',
    });
  }

  onEditFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.editSelectedFile.set(input.files[0]);
    }
  }

  closeEditDoc(): void {
    this.showEditDocModal.set(null);
  }

  submitEditDoc(): void {
    const doc = this.showEditDocModal();
    if (!doc || this.editDocForm.invalid) return;

    const vals = this.editDocForm.value;
    const formData = new FormData();
    formData.append('type_document', vals.type_document ?? '');
    if (vals.numero)          formData.append('numero', vals.numero);
    if (vals.date_emission)   formData.append('date_emission', vals.date_emission);
    if (vals.date_expiration) formData.append('date_expiration', vals.date_expiration);
    if (vals.notes)           formData.append('notes', vals.notes);
    // Ajouter le nouveau fichier seulement s'il a été sélectionné
    if (this.editSelectedFile()) {
      formData.append('fichier', this.editSelectedFile()!);
    }

    this.vehiculeApi.updateDocument(this.id(), doc.id, formData).subscribe({
      next: () => {
        this.closeEditDoc();
        this.store.loadVehiculeDetail(this.id());
      },
      error: () => {},
    });
  }

  confirmDeleteDoc(docId: string): void {
    this.deleteDocConfirm.set(docId);
  }

  cancelDeleteDoc(): void {
    this.deleteDocConfirm.set(null);
  }

  doDeleteDoc(docId: string): void {
    this.vehiculeApi.deleteDocument(this.id(), docId).subscribe({
      next: () => {
        this.deleteDocConfirm.set(null);
        this.store.loadVehiculeDetail(this.id());
      },
      error: () => this.deleteDocConfirm.set(null),
    });
  }

  // ── Kilométrage ──
  openKmModal(): void {
    const v = this.store.selectedVehicule();
    this.kmValue.set(v ? v.kilometrage_actuel + 1 : 0);
    this.kmDate.set(new Date().toISOString().split('T')[0]);
    this.kmTypeMouvement.set('releve');
    this.kmChauffeur.set('');
    this.kmTournee.set('');
    this.kmNotes.set('');
    this.kmError.set('');
    this.kmPhoto.set(null);
    this.kmPhotoPreview.set(null);
    this.showKmModal.set(true);
  }

  closeKmModal(): void {
    this.showKmModal.set(false);
    this.kmLoading.set(false);
    this.kmError.set('');
    this.kmPhoto.set(null);
    this.kmPhotoPreview.set(null);
  }

  onKmPhotoChange(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.kmPhoto.set(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => this.kmPhotoPreview.set(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      this.kmPhotoPreview.set(null);
    }
  }

  openPhotoLightbox(url: string): void { this.photoLightbox.set(url); }
  closePhotoLightbox(): void           { this.photoLightbox.set(null); }

  onKmInput(event: Event): void {
    this.kmValue.set(parseInt((event.target as HTMLInputElement).value, 10) || 0);
  }

  onKmDateInput(event: Event): void {
    this.kmDate.set((event.target as HTMLInputElement).value);
  }

  onKmTypeMouvement(event: Event): void {
    this.kmTypeMouvement.set((event.target as HTMLSelectElement).value as any);
  }

  onKmChauffeur(event: Event): void {
    this.kmChauffeur.set((event.target as HTMLSelectElement).value);
  }

  onKmTournee(event: Event): void {
    this.kmTournee.set((event.target as HTMLInputElement).value);
  }

  onKmNotes(event: Event): void {
    this.kmNotes.set((event.target as HTMLTextAreaElement).value);
  }

  saveKilometrage(): void {
    const v = this.store.selectedVehicule();
    if (!v) return;

    const km = this.kmValue();
    if (!km || km <= 0) {
      this.kmError.set('Veuillez saisir un kilométrage valide.');
      return;
    }

    // Avertissement si inférieur (pas bloquant - on laisse passer)
    const type = this.kmTypeMouvement();
    if (type === 'releve' && km < v.kilometrage_actuel) {
      this.kmError.set(
        `⚠️ Ce kilométrage (${km.toLocaleString('fr-FR')} km) est inférieur au kilométrage actuel (${v.kilometrage_actuel.toLocaleString('fr-FR')} km). L'enregistrement continue.`
      );
      // On NE fait PAS return — on laisse l'enregistrement se faire
    }

    this.kmLoading.set(true);
    this.kmError.set('');
    this.vehiculeApi.updateKilometrage(this.id(), {
      kilometrage:          km,
      date_releve:          this.kmDate(),
      type_mouvement:       this.kmTypeMouvement(),
      chauffeur:            this.kmChauffeur() || undefined,
      tournee:              this.kmTournee() || undefined,
      notes:                this.kmNotes() || undefined,
      photo_tableau_bord:   this.kmPhoto() || null,
    }).subscribe({
      next: () => {
        this.kmLoading.set(false);
        this.closeKmModal();
        this.store.loadVehiculeDetail(this.id());
      },
      error: (err) => {
        this.kmLoading.set(false);
        this.kmError.set(err?.error?.detail ?? 'Erreur lors de la mise à jour.');
      },
      complete: () => {
        this.kmLoading.set(false);
      },
    });
  }

  openImmatModal(): void {
    this.immatError.set('');
    this.immatSuccess.set('');
    this.newImmat.set('');
    this.dateImmat.set(new Date().toISOString().split('T')[0]);
    this.motifImmat.set('Passage de provisoire à définitive');
    this.showImmatModal.set(true);
    // Charger l'historique
    this.vehiculeApi.getHistoriqueImmat(this.id()).subscribe({
      next: (list) => this.historiqueImmat.set(list),
      error: () => {},
    });
  }

  closeImmatModal(): void { this.showImmatModal.set(false); }

  onNewImmat(event: Event): void {
    this.newImmat.set((event.target as HTMLInputElement).value.toUpperCase());
  }

  onDateImmat(event: Event): void {
    this.dateImmat.set((event.target as HTMLInputElement).value);
  }

  onMotifImmat(event: Event): void {
    this.motifImmat.set((event.target as HTMLInputElement).value);
  }

  submitChangerImmat(): void {
    if (!this.newImmat() || this.immatLoading()) return;
    this.immatLoading.set(true);
    this.immatError.set('');

    this.vehiculeApi.changerImmatriculation(this.id(), {
      nouvelle_immatriculation: this.newImmat(),
      date_changement:          this.dateImmat(),
      motif:                    this.motifImmat(),
    }).subscribe({
      next: (res) => {
        this.immatLoading.set(false);
        this.immatSuccess.set(res.detail);
        this.closeImmatModal();
        this.store.loadVehiculeDetail(this.id());
      },
      error: (err) => {
        this.immatLoading.set(false);
        this.immatError.set(err?.error?.detail ?? "Erreur lors du changement.");
      },
    });
  }

  typeMouvementClass(type: string): string {
    const map: Record<string, string> = {
      entree: 'badge-green', sortie: 'badge-warning',
      releve: 'badge-navy',  tournee: 'badge-info',
    };
    return map[type] ?? 'badge-gray';
  }

  goToEdit(): void { this.router.navigate(['/vehicules', this.id(), 'modifier']); }
  goToRelevesKm(): void { this.router.navigate(['/vehicules', this.id(), 'releves-km']); }
  goBack(): void   { this.router.navigate(['/vehicules']); }

  statutBadgeClass(couleur: string): string {
    const map: Record<string, string> = {
      green: 'badge-green', orange: 'badge-warning',
      red: 'badge-danger', blue: 'badge-blue', gray: 'badge-gray',
    };
    return map[couleur] ?? 'badge-gray';
  }

  interventionStatutClass(statut: StatutIntervention): string {
    const map: Record<StatutIntervention, string> = {
      planifie: 'badge-navy', en_cours: 'badge-info',
      termine: 'badge-green', annule: 'badge-gray', attente_piece: 'badge-warning',
    };
    return map[statut] ?? 'badge-gray';
  }

  statutValidationClass(statut: string): string {
    const map: Record<string, string> = {
      normal: 'badge-green', anomalie: 'badge-danger',
      en_attente: 'badge-warning', valide: 'badge-green',
    };
    return map[statut] ?? 'badge-gray';
  }

  // ── Onglet Statut ──────────────────────────────────────────────
  historiqueStatuts      = signal<any[]>([]);
  historiqueStatutsLoad  = signal(false);
  statutsDisponibles     = signal<any[]>([]);
  showChangerStatutModal = signal(false);

  changerStatutForm = this.fb.group({
    nouveau_statut:   [null as number | null, [Validators.required]],
    motif:            [''],
    date_changement:  [new Date().toISOString().substring(0, 10), [Validators.required]],
  });

  loadHistoriqueStatuts(): void {
    const id = this.id();
    if (!id) return;
    this.historiqueStatutsLoad.set(true);
    this.vehiculeApi.getHistoriqueStatuts(id).subscribe({
      next: (l) => { this.historiqueStatuts.set(l); this.historiqueStatutsLoad.set(false); },
      error: () => this.historiqueStatutsLoad.set(false),
    });
  }

  ouvrirChangerStatut(): void {
    if (!this.statutsDisponibles().length) {
      this.parametrageApi.getStatutsVehicule().subscribe({
        next: (l) => { this.statutsDisponibles.set(l.filter((s: any) => s.actif)); },
        error: () => {},
      });
    }
    this.changerStatutForm.reset({
      nouveau_statut: null,
      motif: '',
      date_changement: new Date().toISOString().substring(0, 10),
    });
    this.showChangerStatutModal.set(true);
  }

  fermerChangerStatut(): void {
    this.showChangerStatutModal.set(false);
  }

  sauvegarderChangementStatut(): void {
    if (this.changerStatutForm.invalid) return;
    const id = this.id();
    if (!id) return;
    const vehicule       = this.store.selectedVehicule();
    const nouveauStatut  = this.changerStatutForm.value.nouveau_statut;
    const ancienStatut   = vehicule?.statut ?? null;

    // 1. Mettre à jour le statut du véhicule
    this.vehiculeApi.update(id, { statut: nouveauStatut }).subscribe({
      next: () => {
        // 2. Créer l'entrée dans l'historique
        const data = {
          vehicule:        id,
          ancien_statut:   ancienStatut,
          nouveau_statut:  nouveauStatut,
          motif:           this.changerStatutForm.value.motif || '',
          date_changement: this.changerStatutForm.value.date_changement,
        };
        this.vehiculeApi.createHistoriqueStatut(id, data).subscribe({
          next: () => {
            this.fermerChangerStatut();
            this.loadHistoriqueStatuts();
            this.store.loadVehiculeDetail(id);
          },
          error: () => {
            // Historique échoue mais statut mis à jour — recharger quand même
            this.fermerChangerStatut();
            this.store.loadVehiculeDetail(id);
          },
        });
      },
      error: () => {},
    });
  }

  imprimerFiche(): void {
    const v = this.store.selectedVehicule();
    if (!v) return;
    const titre = `Fiche_Vehicule_${v.immatriculation.replace(/\s/g, '_')}`;
    document.title = titre;
    window.print();
    setTimeout(() => { document.title = 'UbiFleet'; }, 1000);
  }

  couleurStatut(couleur: string): string {
    const map: Record<string, string> = {
      green: 'badge-green', orange: 'badge-warning',
      red: 'badge-danger', blue: 'badge-blue', gray: 'badge-gray',
    };
    return map[couleur] ?? 'badge-gray';
  }
}