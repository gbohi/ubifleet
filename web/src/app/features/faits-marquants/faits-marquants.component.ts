// UbiFleet — Faits marquants (événements notables avec pièce jointe)
//
// Droits : consultation, saisie et suppression selon les permissions par rôle
// (module « faits_marquants », cf. /auth/me/acces/) ; données cloisonnées par agence.
import {
  Component, ChangeDetectionStrategy, OnInit, computed, inject, signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AgenceApiService, FaitsMarquantsApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';

const EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'txt'];
const TAILLE_MAX_MO = 10;

@Component({
  selector: 'ubi-faits-marquants',
  standalone: true,
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './faits-marquants.component.html',
  styleUrls: ['./faits-marquants.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FaitsMarquantsComponent implements OnInit {
  private api       = inject(FaitsMarquantsApiService);
  private agenceApi = inject(AgenceApiService);
  private auth      = inject(AuthService);
  private fb        = inject(FormBuilder);

  readonly accept = EXTENSIONS.map(e => '.' + e).join(',');

  peutSaisir    = computed(() => this.auth.peutAcceder('faits_marquants_ecriture'));
  peutSupprimer = computed(() => this.auth.peutAcceder('faits_marquants_suppression'));
  /** « Toutes les agences » : peut choisir l'agence (ou aucune = concerne tout le monde). */
  toutesAgences = computed(() => !this.auth.currentUser()?.agence);

  faits      = signal<any[]>([]);
  total      = signal(0);
  page       = signal(1);
  chargement = signal(true);
  recherche  = signal('');
  dateDebut  = signal('');
  dateFin    = signal('');
  notice     = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);
  agences    = signal<any[]>([]);

  readonly parPage = 20;
  nbPages = computed(() => Math.max(1, Math.ceil(this.total() / this.parPage)));

  // Fenêtre de saisie
  faitEdite      = signal<any | null | undefined>(undefined);   // undefined = fermée, null = création
  fichier        = signal<File | null>(null);
  supprimerDoc   = signal(false);
  erreurForm     = signal('');
  enregistrement = signal(false);
  form = this.fb.group({
    libelle:     ['', [Validators.required, Validators.maxLength(200)]],
    date:        [new Date().toISOString().split('T')[0], Validators.required],
    description: [''],
    agence:      [null as string | null],
  });

  ngOnInit(): void {
    this.charger();
    if (this.toutesAgences()) {
      this.agenceApi.getAll().subscribe({ next: (l: any) => this.agences.set(Array.isArray(l) ? l : l.results ?? []), error: () => {} });
    }
  }

  charger(): void {
    this.chargement.set(true);
    this.api.getAll({
      page: this.page(), page_size: this.parPage, search: this.recherche(),
      date_debut: this.dateDebut(), date_fin: this.dateFin(),
    }).subscribe({
      next: res => { this.faits.set(res.results ?? []); this.total.set(res.count ?? 0); this.chargement.set(false); },
      error: () => { this.chargement.set(false); this.notice.set({ type: 'err', texte: 'Impossible de charger les faits marquants.' }); },
    });
  }

  filtrer(): void { this.page.set(1); this.charger(); }
  allerPage(p: number): void { this.page.set(p); this.charger(); }

  ouvrir(f: any | null): void {
    this.erreurForm.set('');
    this.fichier.set(null);
    this.supprimerDoc.set(false);
    this.form.reset(f
      ? { libelle: f.libelle, date: f.date, description: f.description, agence: f.agence }
      : { libelle: '', date: new Date().toISOString().split('T')[0], description: '', agence: null });
    this.faitEdite.set(f);
  }

  onFichier(e: Event): void {
    const f = (e.target as HTMLInputElement).files?.[0] ?? null;
    this.erreurForm.set('');
    if (f) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
      if (!EXTENSIONS.includes(ext)) {
        this.erreurForm.set(`Format non accepté. Formats autorisés : ${EXTENSIONS.join(', ')}.`);
        (e.target as HTMLInputElement).value = '';
        return;
      }
      if (f.size > TAILLE_MAX_MO * 1024 * 1024) {
        this.erreurForm.set(`Le document ne doit pas dépasser ${TAILLE_MAX_MO} Mo.`);
        (e.target as HTMLInputElement).value = '';
        return;
      }
    }
    this.fichier.set(f);
    this.supprimerDoc.set(false);
  }

  enregistrer(): void {
    if (this.form.invalid || this.enregistrement()) return;
    const v = this.form.value;
    const fd = new FormData();
    fd.append('libelle', v.libelle ?? '');
    fd.append('date', v.date ?? '');
    fd.append('description', v.description ?? '');
    if (this.toutesAgences()) fd.append('agence', v.agence ?? '');
    if (this.fichier()) fd.append('document', this.fichier()!);
    else if (this.supprimerDoc()) fd.append('document', '');

    const f = this.faitEdite();
    this.enregistrement.set(true);
    (f ? this.api.update(f.id, fd) : this.api.create(fd)).subscribe({
      next: () => {
        this.enregistrement.set(false);
        this.faitEdite.set(undefined);
        this.notice.set({ type: 'ok', texte: f ? 'Fait marquant modifié.' : 'Fait marquant enregistré.' });
        this.charger();
      },
      error: (err: any) => {
        this.enregistrement.set(false);
        const e = err?.error ?? {};
        this.erreurForm.set(e.detail ?? (e.document ? `Document : ${[].concat(e.document).join(' ')}` : null)
          ?? Object.values(e).flat().join(' ') ?? "Erreur lors de l'enregistrement.");
      },
    });
  }

  supprimer(f: any): void {
    if (!confirm(`Supprimer le fait marquant « ${f.libelle} » et son document ?`)) return;
    this.api.delete(f.id).subscribe({
      next: () => { this.notice.set({ type: 'ok', texte: 'Fait marquant supprimé.' }); this.charger(); },
      error: (err: any) => this.notice.set({ type: 'err', texte: err?.error?.detail ?? 'Suppression impossible.' }),
    });
  }

  /** Un fait « toutes agences » ne se modifie que par un utilisateur sans agence. */
  modifiable(f: any): boolean {
    return this.peutSaisir() && (!!f.agence || this.toutesAgences());
  }
}
