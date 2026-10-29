// UbiFleet — Demandes (Angular 18)
import {
  Component, inject, OnInit, ChangeDetectionStrategy, signal
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  DemandesApiService, AgenceApiService, ChauffeurApiService, RoleApiService
} from '../../core/services/api.service';

type Tab = 'liste' | 'nouvelle' | 'a_valider' | 'types';

interface LigneAchat {
  id?: number;
  designation: string;
  quantite:    number;
  unite:       string;
  prix_unitaire: number | null;
  fournisseur: string;
  notes:       string;
}

@Component({
  selector: 'ubi-demandes',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './demandes.component.html',
  styleUrls:   ['./demandes.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DemandesComponent implements OnInit {
  private api         = inject(DemandesApiService);
  private agenceApi   = inject(AgenceApiService);
  private chauffeurApi= inject(ChauffeurApiService);
  private roleApi     = inject(RoleApiService);
  private fb          = inject(FormBuilder);

  activeTab = signal<Tab>('liste');
  stats     = signal<any>(null);

  // ── Liste demandes ────────────────────────────────────────────────
  demandes        = signal<any[]>([]);
  demandesTotal   = signal(0);
  demandesLoading = signal(false);
  vue             = signal('mes_demandes');
  filtreStatut    = signal('');
  filtrePrio      = signal('');
  filtreType      = signal('');
  filtreDebut     = signal('');
  filtreFin       = signal('');
  filtrePage      = signal(1);
  readonly pageSize = 20;

  // ── À valider ─────────────────────────────────────────────────────
  aValider          = signal<any[]>([]);
  aValiderLoading   = signal(false);
  aValiderStatut    = signal('');
  aValiderPrio      = signal('');
  aValiderType      = signal('');
  aValiderDebut     = signal('');
  aValiderFin       = signal('');
  validationModal   = signal<any>(null);
  valCommentaire    = signal('');
  valRejet          = signal(false);
  valLoading        = signal(false);

  // ── Nouvelle demande ──────────────────────────────────────────────
  typesDemande = signal<any[]>([]);
  agences      = signal<any[]>([]);
  chauffeurs   = signal<any[]>([]);
  newLoading   = signal(false);
  newError     = signal('');
  newSuccess   = signal('');
  showMateriel = signal(false);
  showVehicule = signal(false);

  // Lignes d'achat (multi-lignes pour code='achat')
  lignesAchat = signal<LigneAchat[]>([]);

  get totalAchat(): number {
    return this.lignesAchat().reduce((sum, l) => {
      const pu = Number(l.prix_unitaire) || 0;
      return sum + (Number(l.quantite) || 0) * pu;
    }, 0);
  }

  demandeForm = this.fb.group({
    type_demande:        ['', Validators.required],
    titre:               ['', Validators.required],
    description:         ['', Validators.required],
    priorite:            ['normale'],
    date_souhaitee:      [''],
    agence:              [''],
    vehicule:            [''],
    chauffeur:           [''],
    materiel:            [''],
    quantite:            [null as number | null],
    unite:               [''],
    fournisseur_suggere: [''],
    montant_estime:      [null as number | null],
  });

  // ── Types de demande ──────────────────────────────────────────────
  typeLoading    = signal(false);
  typeError      = signal('');
  typeSuccess    = signal('');
  editTypeId     = signal<string | null>(null);
  showTypeModal  = signal(false);
  // Popup suppression type
  deleteTypeConfirm = signal<any>(null);
  deleteTypeLoading = signal(false);
  roles = signal<any[]>([]);

  typeForm = this.fb.group({
    code:                ['autre'],
    nom:                 ['', Validators.required],
    nb_niveaux:          [2, [Validators.required, Validators.min(1), Validators.max(4)]],
    delai_reponse_jours: [3],
    actif:               [true],
  });

  // ── Niveaux de validation ─────────────────────────────────────────
  niveauxActifs         = signal<any[]>([]);
  niveauxLoading        = signal(false);
  editingTypeForNiveaux = signal<any>(null);
  // Popup suppression niveau
  deleteNiveauConfirm   = signal<any>(null);
  deleteNiveauLoading   = signal(false);

  niveauForm = this.fb.group({
    niveau:   [1, [Validators.required, Validators.min(1), Validators.max(4)]],
    libelle:  ['', Validators.required],
    role_min: [null as number | null],
  });
  // ── Popup annulation demande ──────────────────────────────────────
  annulerConfirm  = signal<string | null>(null);
  annulerLoading  = signal(false);

  ngOnInit(): void {
    this.loadDemandes();
    this.loadStats();
    this.loadAValider();
    this.api.getTypesDemande(true).subscribe({
      next: (l) => this.typesDemande.set(l), error: () => {}
    });
    this.agenceApi.getAll().subscribe({
      next: (r: any) => this.agences.set(r.results ?? r ?? []), error: () => {}
    });
    this.chauffeurApi.getAll({ page_size: 200 }).subscribe({
      next: (r: any) => this.chauffeurs.set(
        (r.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ), error: () => {}
    });
    this.demandeForm.get('type_demande')?.valueChanges.subscribe(id => {
      const t = this.typesDemande().find(td => td.id === Number(id) || td.id === id);
      if (t) {
        const isAchat = t.code === 'achat';
        this.showMateriel.set(isAchat);
        this.showVehicule.set(['vehicule', 'entretien', 'carburant'].includes(t.code));
        if (isAchat && this.lignesAchat().length === 0) {
          this.ajouterLigne(); // ajouter une ligne vide par défaut
        }
      }
    });
    this.roleApi.getAll().subscribe({
      next: (list) => this.roles.set(
        Array.isArray(list) ? list : (list as any).results ?? []
      ), error: () => {}
    });
  }

  // ── Chargement ────────────────────────────────────────────────────
  loadDemandes(): void {
    this.demandesLoading.set(true);
    const params: Record<string, any> = {
      vue: this.vue(), page: this.filtrePage(), page_size: this.pageSize
    };
    if (this.filtreStatut()) params['statut']       = this.filtreStatut();
    if (this.filtrePrio())   params['priorite']     = this.filtrePrio();
    if (this.filtreType())   params['type_demande'] = this.filtreType();
    if (this.filtreDebut())  params['date_debut']   = this.filtreDebut();
    if (this.filtreFin())    params['date_fin']     = this.filtreFin();
    this.api.getDemandes(params).subscribe({
      next: (r: any) => {
        this.demandes.set(r.results ?? r ?? []);
        this.demandesTotal.set(r.count ?? 0);
        this.demandesLoading.set(false);
      },
      error: () => this.demandesLoading.set(false),
    });
  }

  loadStats(): void {
    this.api.getStats(this.vue()).subscribe({
      next: s => this.stats.set(s), error: () => {}
    });
  }

  loadAValider(): void {
    this.aValiderLoading.set(true);
    const params: Record<string, any> = {};
    if (this.aValiderStatut()) params['statut']       = this.aValiderStatut();
    if (this.aValiderPrio())   params['priorite']     = this.aValiderPrio();
    if (this.aValiderType())   params['type_demande'] = this.aValiderType();
    if (this.aValiderDebut())  params['date_debut']   = this.aValiderDebut();
    if (this.aValiderFin())    params['date_fin']     = this.aValiderFin();
    this.api.getAValider().subscribe({
      next: (l) => { this.aValider.set(l); this.aValiderLoading.set(false); },
      error: () => this.aValiderLoading.set(false),
    });
  }

  // ── Filtres ───────────────────────────────────────────────────────
  onVueChange(v: string): void {
    this.vue.set(v); this.filtrePage.set(1);
    this.loadDemandes(); this.loadStats();
  }

  onFiltreChange(field: string, e: Event): void {
    const val = (e.target as HTMLSelectElement | HTMLInputElement).value;
    if (field === 'statut') this.filtreStatut.set(val);
    if (field === 'prio')   this.filtrePrio.set(val);
    if (field === 'type')   this.filtreType.set(val);
    if (field === 'debut')  this.filtreDebut.set(val);
    if (field === 'fin')    this.filtreFin.set(val);
    this.filtrePage.set(1);
    this.loadDemandes();
  }

  onFiltreAValiderChange(field: string, e: Event): void {
    const val = (e.target as HTMLSelectElement | HTMLInputElement).value;
    if (field === 'statut') this.aValiderStatut.set(val);
    if (field === 'prio')   this.aValiderPrio.set(val);
    if (field === 'type')   this.aValiderType.set(val);
    if (field === 'debut')  this.aValiderDebut.set(val);
    if (field === 'fin')    this.aValiderFin.set(val);
    this.loadAValider();
  }

  // ── Gestion lignes achat ─────────────────────────────────────────
  ajouterLigne(): void {
    this.lignesAchat.set([...this.lignesAchat(), {
      designation: '', quantite: 1, unite: 'unités',
      prix_unitaire: null, fournisseur: '', notes: ''
    }]);
  }

  supprimerLigne(i: number): void {
    const l = [...this.lignesAchat()];
    l.splice(i, 1);
    this.lignesAchat.set(l);
  }

  updateLigne(i: number, field: keyof LigneAchat, e: Event): void {
    const val = (e.target as HTMLInputElement).value;
    const l = [...this.lignesAchat()];
    if (field === 'quantite' || field === 'prix_unitaire') {
      (l[i] as any)[field] = val === '' ? null : Number(val);
    } else {
      (l[i] as any)[field] = val;
    }
    this.lignesAchat.set(l);
  }

  // ── Créer demande ─────────────────────────────────────────────────
  creerDemande(soumettre = false): void {
    if (this.demandeForm.invalid) return;
    this.newLoading.set(true); this.newError.set('');
    const raw = this.demandeForm.value as any;
    const payload: any = {};
    Object.entries(raw).forEach(([k, v]) => {
      if (v !== null && v !== '' && v !== undefined) payload[k] = v;
    });
    if (payload.type_demande)   payload.type_demande   = Number(payload.type_demande);
    if (payload.quantite)       payload.quantite       = Number(payload.quantite);
    if (payload.montant_estime) payload.montant_estime = Number(payload.montant_estime);

    this.api.createDemande(payload).subscribe({
      next: (d: any) => {
        // Sauvegarder les lignes d'achat si présentes
        const lignes = this.lignesAchat().filter(l => l.designation.trim());
        const saveLignes$ = lignes.length > 0
          ? this.api.bulkSaveLignes(d.id, lignes)
          : null;

        const afterLignes = () => {
          if (soumettre) {
            this.api.soumettre(d.id).subscribe({
              next: () => {
                this.newLoading.set(false);
                this.newSuccess.set('Demande créée et soumise.');
                this.resetNewForm();
                this.loadDemandes(); this.loadStats();
                setTimeout(() => { this.newSuccess.set(''); this.activeTab.set('liste'); }, 1500);
              },
              error: (err: any) => {
                this.newLoading.set(false);
                // Afficher l'erreur réelle pour diagnostic
                const msg = err?.error?.detail ?? JSON.stringify(err?.error) ?? `HTTP ${err?.status}`;
                this.newError.set(`Demande créée mais erreur soumission: ${msg}`);
              },
            });
          } else {
            this.newLoading.set(false);
            this.newSuccess.set('Demande enregistrée en brouillon.');
            this.resetNewForm();
            this.loadDemandes(); this.loadStats();
          }
        };

        if (saveLignes$) {
          saveLignes$.subscribe({
            next: () => afterLignes(),
            error: () => afterLignes(),
          });
        } else {
          afterLignes();
        }
      },
      error: (err: any) => {
        this.newLoading.set(false);
        this.newError.set(err?.error?.detail ?? JSON.stringify(err?.error) ?? 'Erreur.');
      },
    });
  }

  private resetNewForm(): void {
    this.demandeForm.reset({ priorite: 'normale' });
    this.lignesAchat.set([]);
    this.showMateriel.set(false);
    this.showVehicule.set(false);
  }

  soumettreDemande(id: string): void {
    this.api.soumettre(id).subscribe({ next: () => this.loadDemandes(), error: () => {} });
  }

  // ── Annulation avec popup ─────────────────────────────────────────
  demanderAnnulation(id: string): void  { this.annulerConfirm.set(id); }
  annulerConfirmCancel(): void           { this.annulerConfirm.set(null); }

  confirmerAnnulation(): void {
    const id = this.annulerConfirm();
    if (!id) return;
    this.annulerLoading.set(true);
    this.api.annuler(id).subscribe({
      next: () => {
        this.annulerLoading.set(false);
        this.annulerConfirm.set(null);
        this.loadDemandes(); this.loadStats();
      },
      error: () => { this.annulerLoading.set(false); this.annulerConfirm.set(null); },
    });
  }

  // ── Validation ────────────────────────────────────────────────────
  ouvrirValidation(d: any, rejet = false): void {
    this.validationModal.set(d);
    this.valCommentaire.set('');
    this.valRejet.set(rejet);
  }
  fermerValidation(): void { this.validationModal.set(null); }

  confirmerValidation(): void {
    const d = this.validationModal();
    if (!d) return;
    if (this.valRejet() && !this.valCommentaire().trim()) return;
    this.valLoading.set(true);
    const req = this.valRejet()
      ? this.api.rejeter(d.id, this.valCommentaire())
      : this.api.valider(d.id, this.valCommentaire());
    req.subscribe({
      next: () => {
        this.valLoading.set(false);
        this.fermerValidation();
        this.loadAValider(); this.loadDemandes(); this.loadStats();
      },
      error: (err: any) => {
        this.valLoading.set(false);
        const msg = err?.error?.detail ?? JSON.stringify(err?.error) ?? 'Erreur.';
        this.typeError.set(msg);
      },
    });
  }

  onValCommentaire(e: Event): void {
    this.valCommentaire.set((e.target as HTMLTextAreaElement).value);
  }

  // ── Types CRUD ────────────────────────────────────────────────────
  loadTypes(): void {
    this.api.getTypesDemande().subscribe({ next: (l) => this.typesDemande.set(l), error: () => {} });
  }

  ouvrirNouveauType(): void {
    this.editTypeId.set(null);
    this.typeError.set('');
    this.typeForm.reset({ code: 'autre', nb_niveaux: 2, delai_reponse_jours: 3, actif: true });
    this.showTypeModal.set(true);
  }

  editType(t: any): void {
    this.editTypeId.set(t.id);
    this.typeError.set('');
    this.typeForm.patchValue({
      code: t.code, nom: t.nom,
      nb_niveaux: t.nb_niveaux,
      delai_reponse_jours: t.delai_reponse_jours,
      actif: t.actif,
    });
    this.showTypeModal.set(true);
  }

  cancelEditType(): void {
    this.editTypeId.set(null);
    this.showTypeModal.set(false);
    this.typeForm.reset({ code: 'autre', nb_niveaux: 2, delai_reponse_jours: 3, actif: true });
  }

  saveType(): void {
    if (this.typeForm.invalid) return;
    const id  = this.editTypeId();
    const req = id
      ? this.api.updateTypeDemande(id, this.typeForm.value)
      : this.api.createTypeDemande(this.typeForm.value);
    req.subscribe({
      next: () => {
        this.showTypeModal.set(false);
        this.typeSuccess.set(id ? 'Type modifié.' : 'Type créé.');
        this.cancelEditType();
        this.loadTypes();
        setTimeout(() => this.typeSuccess.set(''), 3000);
      },
      error: (err: any) => this.typeError.set(err?.error?.detail ?? 'Erreur.'),
    });
  }

  // Suppression type avec popup
  demanderSuppressionType(t: any): void  { this.deleteTypeConfirm.set(t); }
  annulerSuppressionType(): void          { this.deleteTypeConfirm.set(null); }

  confirmerSuppressionType(): void {
    const t = this.deleteTypeConfirm();
    if (!t) return;
    this.deleteTypeLoading.set(true);
    this.api.updateTypeDemande(t.id, { actif: false }).subscribe({
      next: () => {
        this.deleteTypeLoading.set(false);
        this.deleteTypeConfirm.set(null);
        this.loadTypes();
      },
      error: (err: any) => {
        this.deleteTypeLoading.set(false);
        this.typeError.set(err?.error?.detail ?? 'Erreur lors de la suppression.');
      },
    });
  }

  // ── Niveaux CRUD ──────────────────────────────────────────────────
  ouvrirNiveaux(t: any): void {
    this.editingTypeForNiveaux.set(t);
    this.loadNiveaux(t.id);
    this.niveauForm.reset({ niveau: (t.niveaux?.length ?? 0) + 1, libelle: '', role_min: null });
  }

  fermerNiveaux(): void {
    this.editingTypeForNiveaux.set(null);
    this.niveauxActifs.set([]);
  }

  loadNiveaux(typeId: string | number): void {
    this.niveauxLoading.set(true);
    this.api.getNiveaux(typeId).subscribe({
      next: (list) => { this.niveauxActifs.set(list); this.niveauxLoading.set(false); },
      error: () => this.niveauxLoading.set(false),
    });
  }

  saveNiveau(): void {
    if (this.niveauForm.invalid) return;
    const t = this.editingTypeForNiveaux();
    if (!t) return;
    // Vérifier qu'on ne dépasse pas le nb_niveaux défini sur le type
    if (this.niveauxActifs().length >= t.nb_niveaux) {
      this.typeError.set(
        `Ce type est limité à ${t.nb_niveaux} niveau(x) de validation. ` +
        `Modifiez le type pour augmenter ce nombre.`
      );
      return;
    }
    const val = this.niveauForm.value;
    const data: any = {
      type_demande: t.id,
      niveau:       Number(val.niveau),
      libelle:      val.libelle,
    };
    // role_min est un UUID string — on l'envoie tel quel si non vide/null
    const rmRaw = val.role_min;
    const rmStr = rmRaw !== null && rmRaw !== undefined ? String(rmRaw) : '';
    if (rmStr !== '' && rmStr !== 'null') {
      data.role_min = rmStr;   // UUID string, pas de conversion Number()
    }
    this.api.createNiveau(data).subscribe({
      next: () => {
        this.loadNiveaux(t.id);
        this.niveauForm.reset({ niveau: this.niveauxActifs().length + 2, libelle: '', role_min: null });
        this.loadTypes();
      },
      error: (err: any) => {
        this.typeError.set(err?.error?.detail ?? JSON.stringify(err?.error) ?? 'Erreur.');
      },
    });
  }

  // Suppression niveau avec popup
  demanderSuppressionNiveau(n: any): void { this.deleteNiveauConfirm.set(n); }
  annulerSuppressionNiveau(): void         { this.deleteNiveauConfirm.set(null); }

  confirmerSuppressionNiveau(): void {
    const n = this.deleteNiveauConfirm();
    if (!n) return;
    const t = this.editingTypeForNiveaux();
    this.deleteNiveauLoading.set(true);
    this.api.deleteNiveau(n.id).subscribe({
      next: () => {
        this.deleteNiveauLoading.set(false);
        this.deleteNiveauConfirm.set(null);
        if (t) this.loadNiveaux(t.id);
        this.loadTypes();
      },
      error: () => { this.deleteNiveauLoading.set(false); this.deleteNiveauConfirm.set(null); },
    });
  }

  // ── Détail d'une demande ──────────────────────────────────────────
  demandeDetail        = signal<any>(null);
  demandeDetailLoading = signal(false);

  voirDetail(d: any): void {
    this.demandeDetailLoading.set(true);
    this.demandeDetail.set(d); // afficher les infos de base immédiatement
    this.api.getDemande(d.id).subscribe({
      next: (detail) => { this.demandeDetail.set(detail); this.demandeDetailLoading.set(false); },
      error: () => this.demandeDetailLoading.set(false),
    });
  }

  fermerDetail(): void { this.demandeDetail.set(null); }
  statutClass(s: string): string {
    const m: Record<string, string> = {
      brouillon: 'badge-gray', soumise: 'badge-warning',
      en_validation: 'badge-warning', approuvee: 'badge-green',
      rejetee: 'badge-danger', annulee: 'badge-gray', cloturee: 'badge-gray',
    };
    return m[s] ?? 'badge-gray';
  }

  prioriteClass(p: string): string {
    const m: Record<string, string> = {
      basse: 'badge-gray', normale: 'badge-navy', haute: 'badge-warning', urgente: 'badge-danger',
    };
    return m[p] ?? 'badge-gray';
  }

  typeIcon(code: string): string {
    const m: Record<string, string> = {
      vehicule: 'fas fa-car', entretien: 'fas fa-tools',
      carburant: 'fas fa-gas-pump', achat: 'fas fa-shopping-cart', autre: 'fas fa-file-alt',
    };
    return m[code] ?? 'fas fa-file-alt';
  }

  get totalPages(): number { return Math.ceil(this.demandesTotal() / this.pageSize) || 1; }
  get pages(): number[] {
    const t = this.totalPages, c = this.filtrePage(), r: number[] = [];
    for (let i = Math.max(1, c - 2); i <= Math.min(t, c + 2); i++) r.push(i);
    return r;
  }
}
