// UbiFleet — Contrôle Véhicule Détail / Rapport
import {
  Component, inject, OnInit, ChangeDetectionStrategy, signal
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe, KeyValuePipe, TitleCasePipe } from '@angular/common';
import { ControleApiService } from '../../../core/services/api.service';

interface PointEdit { statut: string; gravite: string; remarque: string; }

@Component({
  selector: 'ubi-controle-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, KeyValuePipe, TitleCasePipe],
  templateUrl: './controle-detail.component.html',
  styleUrls:   ['./controle-detail.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ControleDetailComponent implements OnInit {
  private api    = inject(ControleApiService);
  private route  = inject(ActivatedRoute);
  private router = inject(Router);

  fiche       = signal<any>(null);
  loading     = signal(true);
  error       = signal('');
  ficheId     = '';

  editMode    = signal(false);
  pointsEdit  = signal<Record<number, PointEdit>>({});
  saving      = signal(false);
  saveSuccess = signal('');
  saveError   = signal('');

  get isValidee(): boolean {
    const s = this.fiche()?.statut_global;
    return s === 'conforme' || s === 'non_conforme' || s === 'partiel';
  }

  get categoriesGroupes(): Record<string, any[]> {
    const f = this.fiche();
    if (!f?.points?.length) return {};
    const g: Record<string, any[]> = {};
    for (const p of f.points) {
      const cat = p.element_categorie || 'autre';
      if (!g[cat]) g[cat] = [];
      g[cat].push(p);
    }
    return g;
  }

  get statsFiche(): { total: number; conformes: number; nc: number; na: number; taux: number } {
    const f = this.fiche();
    if (!f?.points?.length) return { total: 0, conformes: 0, nc: 0, na: 0, taux: 0 };
    const total    = f.points.length;
    const conformes= f.points.filter((p: any) => p.statut === 'conforme').length;
    const nc       = f.points.filter((p: any) => p.statut === 'non_conforme').length;
    const na       = f.points.filter((p: any) => p.statut === 'na').length;
    const taux     = total > 0 ? Math.round((conformes / Math.max(total - na, 1)) * 100) : 0;
    return { total, conformes, nc, na, taux };
  }

  get pointsNonConformes(): any[] {
    return this.fiche()?.points?.filter((p: any) => p.statut === 'non_conforme') ?? [];
  }

  ngOnInit(): void {
    this.ficheId = this.route.snapshot.paramMap.get('id') ?? '';
    if (!this.ficheId) { this.router.navigate(['/controle']); return; }
    this.loadFiche();
  }

  loadFiche(): void {
    this.loading.set(true);
    this.api.getFiche(this.ficheId).subscribe({
      next: (f) => {
        this.fiche.set(f);
        this.loading.set(false);
        this.initPointsEdit(f);
      },
      error: () => {
        this.error.set('Fiche introuvable ou erreur de chargement.');
        this.loading.set(false);
      },
    });
  }

  initPointsEdit(f: any): void {
    const m: Record<number, PointEdit> = {};
    for (const p of (f.points ?? [])) {
      m[p.element] = {
        statut:   p.statut   ?? 'conforme',
        gravite:  p.gravite  ?? '',
        remarque: p.remarque ?? '',
      };
    }
    this.pointsEdit.set(m);
  }

  toggleEditMode(): void {
    if (this.isValidee) return;
    this.editMode.set(!this.editMode());
    if (!this.editMode()) this.saveError.set('');
  }

  getPointEdit(elementId: number): PointEdit {
    return this.pointsEdit()[elementId] ?? { statut: 'conforme', gravite: '', remarque: '' };
  }

  setPoint(elementId: number, field: keyof PointEdit, val: string): void {
    const m = { ...this.pointsEdit() };
    m[elementId] = { ...this.getPointEdit(elementId), [field]: val };
    if (field === 'statut' && val !== 'non_conforme') m[elementId].gravite = '';
    this.pointsEdit.set(m);
  }

  sauvegarderPoints(): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.saveError.set('');
    const points = Object.entries(this.pointsEdit()).map(([id, v]) => ({
      element:  Number(id),
      statut:   v.statut,
      gravite:  v.gravite || null,
      remarque: v.remarque,
    }));
    this.api.bulkSavePoints(this.ficheId, points).subscribe({
      next: () => {
        this.saving.set(false);
        this.saveSuccess.set('Points mis à jour avec succès.');
        this.editMode.set(false);
        this.loadFiche();
        setTimeout(() => this.saveSuccess.set(''), 3000);
      },
      error: () => {
        this.saving.set(false);
        this.saveError.set('Erreur lors de la sauvegarde.');
      },
    });
  }

  validerFiche(): void {
    this.api.validerFiche(this.ficheId).subscribe({
      next: () => this.loadFiche(),
      error: () => {},
    });
  }

  // Lightbox aperçu photo
  lightboxPhoto = signal<{ src: string; alt: string } | null>(null);

  openPhoto(src: string, alt: string): void {
    this.lightboxPhoto.set({ src, alt });
  }

  closeLightbox(): void {
    this.lightboxPhoto.set(null);
  }

  imprimer(): void {
    // Définir le titre de la fenêtre pour le nom du fichier PDF
    const fiche = this.fiche();
    if (fiche) {
      const titre = `Controle_${fiche.vehicule_immat}_${new Date(fiche.date_heure).toLocaleDateString('fr-FR').replace(/\//g,'-')}`;
      document.title = titre;
    }
    window.print();
    // Restaurer le titre après impression
    setTimeout(() => { document.title = 'UbiFleet'; }, 1000);
  }

  statutClass(s: string): string {
    return ({ conforme: 'badge-green', non_conforme: 'badge-danger',
               partiel: 'badge-warning', en_cours: 'badge-gray', na: 'badge-gray' } as Record<string,string>)[s] ?? 'badge-gray';
  }

  graviteClass(g: string): string {
    return ({ mineur: 'badge-warning', majeur: 'badge-orange', bloquant: 'badge-danger' } as Record<string,string>)[g] ?? '';
  }
}
