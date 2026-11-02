// UbiFleet — Chauffeur Detail Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ChauffeurApiService, ParametrageApiService, VehiculeApiService } from '../../../core/services/api.service';
import { Chauffeur, AffectationVehicule, DocumentChauffeur } from '../../../core/models';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';

/** Extensions acceptées (mêmes que le serveur) et taille maximale. */
const EXTENSIONS_DOCUMENT = ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'txt'];
const EXTENSIONS_PHOTO = ['jpg', 'jpeg', 'png', 'webp'];
type Onglet = 'infos' | 'documents' | 'historique' | 'vehicules';

@Component({
  selector: 'ubi-chauffeur-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './chauffeur-detail.component.html',
  styleUrls: ['./chauffeur-detail.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChauffeurDetailComponent implements OnInit {
  id = input.required<string>();

  private router       = inject(Router);
  private chauffeurApi  = inject(ChauffeurApiService);
  private vehiculeApi   = inject(VehiculeApiService);

  chauffeur    = signal<Chauffeur | null>(null);
  historique   = signal<any | null>(null);
  loading      = signal(true);
  error        = signal('');
  activeTab    = signal<Onglet>('infos');
  private fb = inject(FormBuilder);
  private parametrageApi = inject(ParametrageApiService);
  readonly acceptDocuments = EXTENSIONS_DOCUMENT.map(e => '.' + e).join(',');
  readonly acceptPhoto = EXTENSIONS_PHOTO.map(e => '.' + e).join(',');

  // ── Photo ──
  photoEnvoi  = signal(false);
  photoErreur = signal('');

  // ── Documents ──
  documents     = signal<DocumentChauffeur[]>([]);
  documentsLoad = signal(false);
  typesDocument = signal<{ value: string; label: string; actif: boolean }[]>([]);
  docEdite      = signal<DocumentChauffeur | null | undefined>(undefined);   // undefined = fenêtre fermée
  docFichier    = signal<File | null>(null);
  docErreur     = signal('');
  docEnvoi      = signal(false);
  docSurvol     = signal(false);
  docASupprimer = signal<DocumentChauffeur | null>(null);
  apercu        = signal<DocumentChauffeur | null>(null);
  docForm = this.fb.group({
    type_document:   ['', Validators.required],
    libelle:         [''],
    numero:          [''],
    date_emission:   [''],
    date_expiration: [''],
    notes:           [''],
  });

  // ── Onglet Véhicules rattachés ──
  affectations     = signal<AffectationVehicule[]>([]);
  affectationsLoad = signal(false);

  loadAffectations(): void {
    this.affectationsLoad.set(true);
    this.vehiculeApi.getAffectations({ chauffeur: this.id() }).subscribe({
      next: (res) => {
        this.affectations.set(res.results ?? []);
        this.affectationsLoad.set(false);
      },
      error: () => this.affectationsLoad.set(false),
    });
  }

  onTabChange(tab: Onglet): void {
    this.activeTab.set(tab);
    if (tab === 'vehicules' && this.affectations().length === 0) this.loadAffectations();
    if (tab === 'documents') this.loadDocuments();
  }

  // ── Photo ──
  choisirPhoto(e: Event): void {
    const input = e.target as HTMLInputElement;
    const f = input.files?.[0];
    input.value = '';
    if (!f) return;
    const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
    if (!EXTENSIONS_PHOTO.includes(ext)) { this.photoErreur.set('Photo : JPG, PNG ou WEBP uniquement.'); return; }
    if (f.size > 5 * 1024 * 1024) { this.photoErreur.set('La photo ne doit pas dépasser 5 Mo.'); return; }
    this.photoErreur.set(''); this.photoEnvoi.set(true);
    this.chauffeurApi.envoyerPhoto(this.id(), f).subscribe({
      next: c => { this.chauffeur.set(c); this.photoEnvoi.set(false); },
      error: err => { this.photoEnvoi.set(false); this.photoErreur.set(messageErreurApi(err, "Envoi de la photo impossible.")); },
    });
  }
  retirerPhoto(): void {
    if (!confirm('Retirer la photo du chauffeur ?')) return;
    this.chauffeurApi.supprimerPhoto(this.id()).subscribe({ next: c => this.chauffeur.set(c), error: () => {} });
  }

  // ── Documents ──
  loadDocuments(): void {
    this.documentsLoad.set(true);
    this.chauffeurApi.getDocuments(this.id()).subscribe({
      next: l => { this.documents.set(l); this.documentsLoad.set(false); },
      error: () => this.documentsLoad.set(false),
    });
  }
  typesProposes(): { value: string; label: string; actif: boolean }[] {
    const actuel = this.docEdite()?.type_document;
    return this.typesDocument().filter(t => t.actif || t.value === actuel);
  }
  ouvrirDocument(d: DocumentChauffeur | null): void {
    this.docErreur.set(''); this.docFichier.set(null);
    this.docForm.reset({
      type_document: d?.type_document ?? '', libelle: d?.libelle ?? '', numero: d?.numero ?? '',
      date_emission: d?.date_emission ?? '', date_expiration: d?.date_expiration ?? '', notes: d?.notes ?? '',
    });
    this.docEdite.set(d);
  }
  fermerDocument(): void { this.docEdite.set(undefined); }
  choisirFichier(f: File | null | undefined): void {
    if (!f) return;
    const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
    if (!EXTENSIONS_DOCUMENT.includes(ext)) {
      this.docErreur.set(`Format non accepté (.${ext}). Formats : PDF, images (JPG, PNG, WEBP), Word, Excel, OpenDocument, texte.`);
      return;
    }
    if (f.size > 10 * 1024 * 1024) { this.docErreur.set('Le fichier ne doit pas dépasser 10 Mo.'); return; }
    this.docErreur.set(''); this.docFichier.set(f);
  }
  onDocInput(e: Event): void {
    const input = e.target as HTMLInputElement;
    this.choisirFichier(input.files?.[0]);
    input.value = '';
  }
  onDocDrop(e: DragEvent): void { e.preventDefault(); this.docSurvol.set(false); this.choisirFichier(e.dataTransfer?.files?.[0]); }
  enregistrerDocument(): void {
    const edite = this.docEdite();
    if (this.docForm.invalid || this.docEnvoi()) { this.docForm.markAllAsTouched(); return; }
    if (!edite && !this.docFichier()) { this.docErreur.set('Choisissez le fichier à joindre.'); return; }
    const fd = new FormData();
    fd.append('chauffeur', this.id());
    Object.entries(this.docForm.getRawValue()).forEach(([k, v]) => {
      // Création : champs vides omis ; modification : envoyés vides pour être effacés (dates : vide = aucune)
      if (v || edite) fd.append(k, (v as string) ?? '');
    });
    if (this.docFichier()) fd.append('fichier', this.docFichier()!);
    this.docEnvoi.set(true); this.docErreur.set('');
    this.chauffeurApi.enregistrerDocument(fd, edite?.id).subscribe({
      next: () => { this.docEnvoi.set(false); this.fermerDocument(); this.loadDocuments(); this.rafraichirChauffeur(); },
      error: err => { this.docEnvoi.set(false); this.docErreur.set(messageErreurApi(err, "Enregistrement du document impossible.")); },
    });
  }
  confirmerSuppressionDocument(): void {
    const d = this.docASupprimer();
    if (!d) return;
    this.chauffeurApi.supprimerDocument(d.id).subscribe({
      next: () => { this.docASupprimer.set(null); this.loadDocuments(); this.rafraichirChauffeur(); },
      error: () => this.docASupprimer.set(null),
    });
  }
  private rafraichirChauffeur(): void {
    this.chauffeurApi.getById(this.id()).subscribe({ next: c => this.chauffeur.set(c), error: () => {} });
  }
  tailleLisible(o: number | null): string {
    if (!o) return '';
    return o < 1024 * 1024 ? `${Math.max(1, Math.round(o / 1024))} Ko` : `${(o / 1024 / 1024).toFixed(1)} Mo`;
  }
  iconeFichier(d: DocumentChauffeur): string {
    const ext = (d.nom_fichier ?? '').split('.').pop()?.toLowerCase() ?? '';
    if (d.est_image) return 'fas fa-file-image';
    if (ext === 'pdf') return 'fas fa-file-pdf';
    if (['doc', 'docx', 'odt', 'txt'].includes(ext)) return 'fas fa-file-word';
    if (['xls', 'xlsx', 'ods'].includes(ext)) return 'fas fa-file-excel';
    return 'fas fa-file';
  }

  ngOnInit(): void {
    this.parametrageApi.getTypesDocumentChauffeur().subscribe({
      next: l => this.typesDocument.set(l.map(t => ({ value: t.code, label: t.libelle, actif: t.actif }))),
      error: () => {},
    });
    this.loadAffectations();
    this.chauffeurApi.getById(this.id()).subscribe({
      next: (c) => {
        this.chauffeur.set(c);
        this.loading.set(false);
        // Charger l'historique en parallèle
        this.chauffeurApi.getHistoriqueCond(this.id()).subscribe({
          next: (h) => this.historique.set(h),
          error: () => {},
        });
      },
      error: (err) => {
        this.error.set(err?.status === 0
          ? 'Serveur inaccessible.'
          : 'Chauffeur introuvable.');
        this.loading.set(false);
      },
    });
  }

  goToEdit(): void {
    this.router.navigate(['/chauffeurs', this.id(), 'modifier']);
  }

  goBack(): void {
    this.router.navigate(['/chauffeurs']);
  }

  permisUrgenceClass(c: Chauffeur): string {
    if (c.permis_expire) return 'expired';
    const j = c.jours_expiration_permis;
    if (j !== null && j <= 30) return 'urgent';
    if (j !== null && j <= 60) return 'warning';
    return 'ok';
  }

  statutBadgeClass(statut: string): string {
    const map: Record<string, string> = {
      actif: 'badge-green', conge: 'badge-info',
      absent: 'badge-warning', suspendu: 'badge-danger', depart: 'badge-gray',
    };
    return map[statut] ?? 'badge-gray';
  }
}
