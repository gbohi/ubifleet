// UbiFleet — Historique Kilométrage (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal, effect, computed
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { VehiculeApiService } from '../../../core/services/api.service';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { HistoriqueCorrectionsComponent } from '../../../shared/corrections/historique-corrections.component';
import { SuppressionMotifComponent } from '../../../shared/corrections/suppression-motif.component';
import { ReleveFormComponent } from '../../../shared/releve-form/releve-form.component';
import { ReleveKilometrage, TypeMouvement } from '../../../core/models';

@Component({
  selector: 'ubi-vehicule-releves-km',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, HistoriqueCorrectionsComponent, SuppressionMotifComponent, ReleveFormComponent],
  templateUrl: './vehicule-releves-km.component.html',
  styleUrls: ['./vehicule-releves-km.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculeRelevesKmComponent implements OnInit {
  id = input.required<string>();

  private router      = inject(Router);
  private route       = inject(ActivatedRoute);
  private vehiculeApi = inject(VehiculeApiService);

  releves     = signal<ReleveKilometrage[]>([]);
  total       = signal(0);
  page        = signal(1);
  loading     = signal(true);
  error       = signal('');
  success     = signal('');
  /** Formulaire ouvert ; `releveEdite` : relevé corrigé (null = nouveau relevé). */
  formOuvert  = signal(false);
  releveEdite = signal<ReleveKilometrage | null>(null);
  releveASupprimer = signal<ReleveKilometrage | null>(null);
  deleteEnCours    = signal(false);
  deleteErreur     = signal('');
  historiqueDe     = signal<ReleveKilometrage | null>(null);
  vehiculeInfo = signal<{ immatriculation: string; designation: string; km: number } | null>(null);
  photoLightbox = signal<string | null>(null);

  // Types de mouvement paramétrables (Paramètres › Types de mouvement)
  typesMvt = inject(TypesMouvementService);

  get totalPages(): number { return Math.ceil(this.total() / 20) || 1; }
  get pages(): number[] {
    const cur = this.page();
    const max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.typesMvt.charger();
    this.loadReleves(this.route.snapshot.queryParamMap.get('modifier'));
    this.rafraichirVehicule();
  }

  /** `aModifier` : relevé à ouvrir en modification (lien depuis une autre page). */
  loadReleves(aModifier?: string | null): void {
    this.loading.set(true);
    this.vehiculeApi.getRelevesKm({ vehicule: this.id(), page: this.page() }).subscribe({
      next: (res) => {
        this.releves.set(res.results ?? []);
        this.total.set(res.count ?? 0);
        this.loading.set(false);
        if (aModifier) {
          const r = this.releves().find(x => x.id === aModifier);
          if (r?.modifiable) this.openForm(r);
          else if (r) this.historiqueDe.set(r);
        }
      },
      error: () => this.loading.set(false),
    });
  }

  openForm(releve?: ReleveKilometrage): void {
    this.success.set('');
    this.releveEdite.set(releve ?? null);
    this.formOuvert.set(true);
  }

  fermerForm(): void { this.formOuvert.set(false); }

  apresEnregistrement(): void {
    this.success.set(this.releveEdite() ? 'Relevé corrigé.' : 'Relevé enregistré.');
    this.formOuvert.set(false);
    this.loadReleves();
    this.rafraichirVehicule();   // km actuel recalculé par le serveur
  }

  openLightbox(url: string): void  { this.photoLightbox.set(url); }
  closeLightbox(): void             { this.photoLightbox.set(null); }

  confirmDelete(r: ReleveKilometrage): void {
    this.deleteErreur.set('');
    this.releveASupprimer.set(r);
  }

  doDelete(motif: string): void {
    const r = this.releveASupprimer();
    if (!r || this.deleteEnCours()) return;
    this.deleteEnCours.set(true);
    this.vehiculeApi.deleteReleveKm(r.id, motif || undefined).subscribe({
      next: () => {
        this.deleteEnCours.set(false);
        this.releveASupprimer.set(null);
        this.success.set('Relevé supprimé.');
        this.loadReleves();
        this.rafraichirVehicule();
      },
      error: (err) => {
        this.deleteEnCours.set(false);
        this.deleteErreur.set(messageErreurApi(err, 'Suppression impossible.'));
      },
    });
  }

  /** Kilométrage actuel du véhicule (recalculé par le serveur après une correction). */
  rafraichirVehicule(): void {
    this.vehiculeApi.getById(this.id()).subscribe({
      next: (v: any) => this.vehiculeInfo.set({
        immatriculation: v.immatriculation, designation: v.designation, km: v.kilometrage_actuel,
      }),
      error: () => {},
    });
  }

  onPageChange(p: number): void { this.page.set(p); this.loadReleves(); }
  goBack(): void { this.router.navigate(['/vehicules', this.id()]); }

  typeMouvementClass(type: TypeMouvement): string {
    return this.typesMvt.classeBadge(type);
  }

  typeMouvementIcon(type: TypeMouvement): string {
    const map: Record<string, string> = {
      entree: 'fa-sign-in-alt', sortie: 'fa-sign-out-alt',
      releve: 'fa-tachometer-alt', tournee: 'fa-route',
    };
    return map[type] ?? 'fa-circle';
  }
}
