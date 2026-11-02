// UbiFleet — Demandes (Angular 18)
import {
  Component, inject, OnInit, ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable, concat, of, forkJoin } from 'rxjs';
import { catchError, last, map, switchMap } from 'rxjs/operators';
import { DemandesApiService, AgenceApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { messageErreurApi } from '../../core/services/fenetre-saisie.service';
import { OptionVehicule, OptionsSaisieService } from '../../core/services/options-saisie.service';
import { OptionRecherche, SelectRechercheComponent } from '../../shared/select-recherche/select-recherche.component';

type Tab = 'liste' | 'a_valider';

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
  imports: [DatePipe, DecimalPipe, ReactiveFormsModule, SelectRechercheComponent],
  templateUrl: './demandes.component.html',
  styleUrls:   ['./demandes.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DemandesComponent implements OnInit {
  private api         = inject(DemandesApiService);
  private agenceApi   = inject(AgenceApiService);
  private options     = inject(OptionsSaisieService);
  private auth        = inject(AuthService);
  private fb          = inject(FormBuilder);

  readonly acceptDocuments = '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.odt,.ods,.txt';
  moi = computed(() => this.auth.currentUser());

  activeTab = signal<Tab>('liste');
  stats     = signal<any>(null);
  messageListe = signal<{ type: 'ok' | 'erreur'; texte: string } | null>(null);

  // ── Liste demandes ────────────────────────────────────────────────
  demandes        = signal<any[]>([]);
  demandesTotal   = signal(0);
  demandesLoading = signal(false);
  vue             = signal('mes_demandes');
  filtreSearch    = signal('');
  filtreStatut    = signal('');
  filtrePrio      = signal('');
  filtreType      = signal('');
  filtreDebut     = signal('');
  filtreFin       = signal('');
  filtrePage      = signal(1);
  readonly pageSize = 20;
  readonly vues = [
    { key: 'mes_demandes',     label: 'Mes demandes' },
    { key: 'validees_par_moi', label: 'Validées par moi' },
    { key: 'agence',           label: 'Mon agence' },
    { key: 'toutes',           label: 'Toutes' },
  ];

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
  valErreur         = signal('');

  // ── Formulaire (popup création / modification) ───────────────────
  typesDemande = signal<any[]>([]);
  /** Types proposés à la saisie (la dotation de tournée se demande depuis Paramètres › Tournées). */
  typesSaisissables = computed(() => this.typesDemande().filter(t =>
    (t.actif !== false && t.code !== 'dotation') || String(t.id) === String(this.typeEdite())));
  agences      = signal<any[]>([]);
  vehicules    = signal<OptionVehicule[]>([]);
  chauffeurs   = signal<OptionRecherche[]>([]);
  formOuvert   = signal(false);
  editId       = signal<string | null>(null);
  private typeEdite = signal<string | number>('');
  formChargement = signal(false);
  newLoading   = signal(false);
  newError     = signal('');
  typeCode     = signal('');
  showMateriel = computed(() => this.typeCode() === 'achat');
  showVehicule = computed(() => ['vehicule', 'entretien', 'carburant'].includes(this.typeCode()));
  /** Fichiers choisis, envoyés à l'enregistrement. */
  fichiersAEnvoyer = signal<File[]>([]);
  /** Pièces déjà jointes (modification). */
  piecesExistantes = signal<any[]>([]);

  // Lignes d'achat (multi-lignes pour code='achat')
  lignesAchat = signal<LigneAchat[]>([]);

  get totalAchat(): number {
    return this.lignesAchat().reduce((sum, l) => {
      const pu = Number(l.prix_unitaire) || 0;
      return sum + (Number(l.quantite) || 0) * pu;
    }, 0);
  }

  demandeForm = this.fb.group({
    type_demande:        ['' as string | number, Validators.required],
    titre:               ['', [Validators.required, Validators.maxLength(200)]],
    description:         ['', Validators.required],
    priorite:            ['normale'],
    date_souhaitee:      [''],
    agence:              [''],
    vehicule:            [''],
    chauffeur:           [''],
    montant_estime:      [null as number | null, Validators.min(0)],
  });

  // ── Popup annulation demande ──────────────────────────────────────
  annulerConfirm  = signal<string | null>(null);
  annulerLoading  = signal(false);

  ngOnInit(): void {
    this.loadDemandes();
    this.loadStats();
    this.loadAValider();
    this.api.getTypesDemande().subscribe({ next: (l) => this.typesDemande.set(l), error: () => {} });
    this.agenceApi.getAll().subscribe({
      next: (r: any) => this.agences.set(r.results ?? r ?? []), error: () => {}
    });
    this.options.vehicules().subscribe({ next: l => this.vehicules.set(l), error: () => {} });
    this.options.chauffeurs().subscribe({ next: l => this.chauffeurs.set(l), error: () => {} });
    this.demandeForm.get('type_demande')?.valueChanges.subscribe(id => {
      const t = this.typesDemande().find(td => String(td.id) === String(id));
      this.typeCode.set(t?.code ?? '');
      if (t?.code === 'achat' && this.lignesAchat().length === 0) this.ajouterLigne();
    });
  }

  // ── Chargement ────────────────────────────────────────────────────
  loadDemandes(): void {
    this.demandesLoading.set(true);
    const params: Record<string, any> = {
      vue: this.vue(), page: this.filtrePage(), page_size: this.pageSize
    };
    if (this.filtreSearch()) params['search']       = this.filtreSearch();
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
    this.api.getAValider(params).subscribe({
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
    if (field === 'search') this.filtreSearch.set(val);
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

  // ── Popup création / modification ────────────────────────────────
  ouvrirFormulaire(d?: any): void {
    this.newError.set(''); this.fichiersAEnvoyer.set([]); this.piecesExistantes.set([]);
    this.lignesAchat.set([]);
    this.editId.set(d?.id ?? null);
    this.typeEdite.set(d?.type_demande ?? '');
    this.demandeForm.reset({ type_demande: '', priorite: 'normale', agence: '', vehicule: '', chauffeur: '' });
    this.typeCode.set('');
    this.formOuvert.set(true);
    if (!d) return;
    this.formChargement.set(true);
    this.api.getDemande(d.id).subscribe({
      next: (x: any) => {
        this.typeEdite.set(x.type_demande ?? this.typesDemande().find(t => t.nom === x.type_nom)?.id ?? '');
        this.lignesAchat.set((x.lignes_achat ?? []).map((l: any) => ({
          id: l.id, designation: l.designation, quantite: Number(l.quantite), unite: l.unite ?? '',
          prix_unitaire: l.prix_unitaire !== null ? Number(l.prix_unitaire) : null,
          fournisseur: l.fournisseur ?? '', notes: l.notes ?? '',
        })));
        this.demandeForm.patchValue({
          type_demande: this.typeEdite(), titre: x.titre, description: x.description ?? '',
          priorite: x.priorite, date_souhaitee: x.date_souhaitee ?? '', agence: x.agence ?? '',
          vehicule: x.vehicule ?? '', chauffeur: x.chauffeur ?? '',
          montant_estime: x.montant_estime !== null ? Number(x.montant_estime) : null,
        });
        this.piecesExistantes.set(x.pieces_jointes ?? []);
        this.formChargement.set(false);
      },
      error: err => { this.formChargement.set(false); this.newError.set(messageErreurApi(err, 'Demande introuvable.')); },
    });
  }

  fermerFormulaire(): void { if (!this.newLoading()) this.formOuvert.set(false); }

  choisirFichiers(e: Event): void {
    const input = e.target as HTMLInputElement;
    const nouveaux = Array.from(input.files ?? []);
    const trop = nouveaux.filter(f => f.size > 10 * 1024 * 1024);
    this.newError.set(trop.length ? `Fichier(s) de plus de 10 Mo ignoré(s) : ${trop.map(f => f.name).join(', ')}` : '');
    this.fichiersAEnvoyer.set([...this.fichiersAEnvoyer(), ...nouveaux.filter(f => f.size <= 10 * 1024 * 1024)]);
    input.value = '';
  }
  retirerFichier(i: number): void {
    const l = [...this.fichiersAEnvoyer()]; l.splice(i, 1); this.fichiersAEnvoyer.set(l);
  }
  supprimerPieceExistante(pj: any): void {
    this.api.supprimerPieceJointe(pj.id).subscribe({
      next: () => this.piecesExistantes.set(this.piecesExistantes().filter(p => p.id !== pj.id)),
      error: err => this.newError.set(messageErreurApi(err, 'Suppression impossible.')),
    });
  }
  taille(o: number): string { return o < 1024 * 1024 ? `${Math.max(1, Math.round(o / 1024))} Ko` : `${(o / 1048576).toFixed(1)} Mo`; }

  enregistrer(soumettre = false): void {
    if (this.demandeForm.invalid || this.newLoading()) { this.demandeForm.markAllAsTouched(); return; }
    const lignes = this.showMateriel() ? this.lignesAchat().filter(l => l.designation.trim()) : [];
    if (this.showMateriel() && lignes.some(l => !(Number(l.quantite) > 0))) {
      this.newError.set('Chaque ligne de matériel doit avoir une quantité positive.'); return;
    }
    this.newLoading.set(true); this.newError.set('');
    const raw = this.demandeForm.getRawValue() as any;
    const vide = (v: any) => v === '' || v === undefined ? null : v;
    const payload: any = {
      type_demande: Number(raw.type_demande), titre: raw.titre.trim(), description: raw.description,
      priorite: raw.priorite, date_souhaitee: vide(raw.date_souhaitee),
      vehicule: this.showVehicule() ? vide(raw.vehicule) : null,
      chauffeur: this.showVehicule() ? vide(raw.chauffeur) : null,
      montant_estime: this.showMateriel() ? null : vide(raw.montant_estime),
    };
    if (raw.agence) payload.agence = raw.agence;
    const id = this.editId();
    const enregistrement$: Observable<any> = id ? this.api.updateDemande(id, payload) : this.api.createDemande(payload);

    let demandeId = id;
    const echecsFichiers: string[] = [];
    enregistrement$.pipe(
      switchMap((d: any) => {
        demandeId = d.id ?? id;
        const etapes: Observable<any>[] = [];
        if (this.showMateriel() || id) etapes.push(this.api.bulkSaveLignes(demandeId!, lignes));
        if (this.fichiersAEnvoyer().length) etapes.push(forkJoin(this.fichiersAEnvoyer().map(f =>
          this.api.envoyerPieceJointe(demandeId!, f).pipe(catchError(err => {
            echecsFichiers.push(`${f.name} : ${messageErreurApi(err, 'envoi impossible')}`); return of(null);
          })))));
        if (soumettre) etapes.push(this.api.soumettre(demandeId!));
        return etapes.length ? concat(...etapes).pipe(last()) : of(d);
      }),
    ).subscribe({
      next: () => {
        this.newLoading.set(false);
        this.formOuvert.set(false);
        const base = soumettre ? 'Demande enregistrée et soumise pour validation.'
                   : id ? 'Demande modifiée.' : 'Demande enregistrée en brouillon.';
        this.messageListe.set(echecsFichiers.length
          ? { type: 'erreur', texte: `${base} Fichiers non joints — ${echecsFichiers.join(' ; ')}` }
          : { type: 'ok', texte: base });
        this.rafraichir();
      },
      error: (err: any) => {
        this.newLoading.set(false);
        if (demandeId && !id) {
          // La demande existe déjà (brouillon) : la suite se fera en modification
          this.editId.set(demandeId);
          this.typeEdite.set(payload.type_demande);
          this.fichiersAEnvoyer.set([]);
          this.api.getDemande(demandeId).subscribe({ next: (x: any) => this.piecesExistantes.set(x.pieces_jointes ?? []), error: () => {} });
          this.rafraichir();
        }
        this.newError.set(messageErreurApi(err, 'Enregistrement impossible.')
          + (demandeId && soumettre ? ' (la demande est enregistrée en brouillon)' : ''));
      },
    });
  }

  private rafraichir(): void { this.loadDemandes(); this.loadStats(); this.loadAValider(); }

  soumettreDemande(id: string): void {
    this.messageListe.set(null);
    this.api.soumettre(id).subscribe({
      next: () => { this.messageListe.set({ type: 'ok', texte: 'Demande soumise pour validation.' }); this.rafraichir();
                    if (this.demandeDetail()?.id === id) this.voirDetail({ id }); },
      error: err => this.messageListe.set({ type: 'erreur', texte: messageErreurApi(err, 'Soumission impossible.') }),
    });
  }

  supprimerConfirm = signal<any>(null);
  supprimerDemande(): void {
    const d = this.supprimerConfirm(); if (!d) return;
    this.api.supprimerDemande(d.id).subscribe({
      next: () => { this.supprimerConfirm.set(null); this.demandeDetail.set(null);
                    this.messageListe.set({ type: 'ok', texte: `Brouillon ${d.numero} supprimé.` }); this.rafraichir(); },
      error: err => { this.supprimerConfirm.set(null); this.messageListe.set({ type: 'erreur', texte: messageErreurApi(err, 'Suppression impossible.') }); },
    });
  }

  estMaDemande(d: any): boolean { return !!d && String(d.demandeur) === String(this.moi()?.id); }
  modifiable(d: any): boolean { return d?.statut === 'brouillon' && d?.type_code !== 'dotation' && (this.estMaDemande(d) || this.moi()?.role === 'super_admin'); }
  modifierDepuisDetail(d: any): void { this.demandeDetail.set(null); this.ouvrirFormulaire(d); }

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
        if (this.demandeDetail()?.id === id) this.demandeDetail.set(null);
        this.messageListe.set({ type: 'ok', texte: 'Demande annulée.' });
        this.rafraichir();
      },
      error: err => { this.annulerLoading.set(false); this.annulerConfirm.set(null);
                      this.messageListe.set({ type: 'erreur', texte: messageErreurApi(err, 'Annulation impossible.') }); },
    });
  }

  // ── Validation ────────────────────────────────────────────────────
  ouvrirValidation(d: any, rejet = false): void {
    this.validationModal.set(d);
    this.valCommentaire.set('');
    this.valRejet.set(rejet);
  }
  fermerValidation(): void { this.validationModal.set(null); this.valErreur.set(''); }

  confirmerValidation(): void {
    const d = this.validationModal();
    if (!d) return;
    if (this.valRejet() && !this.valCommentaire().trim()) return;
    this.valLoading.set(true);
    this.valErreur.set('');
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
        this.valErreur.set(messageErreurApi(err, 'Erreur lors de la validation.'));
      },
    });
  }

  onValCommentaire(e: Event): void {
    this.valCommentaire.set((e.target as HTMLTextAreaElement).value);
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
