// UbiFleet — Chauffeur Detail Component (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ChauffeurApiService, VehiculeApiService } from '../../../core/services/api.service';
import { Chauffeur, AffectationVehicule } from '../../../core/models';

@Component({
  selector: 'ubi-chauffeur-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
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
  activeTab    = signal<'infos' | 'historique' | 'vehicules'>('infos');

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

  onTabChange(tab: 'infos' | 'historique' | 'vehicules'): void {
    this.activeTab.set(tab);
    if (tab === 'vehicules' && this.affectations().length === 0) {
      this.loadAffectations();
    }
  }

  ngOnInit(): void {
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
