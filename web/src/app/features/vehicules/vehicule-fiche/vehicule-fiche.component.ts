// UbiFleet — Fiche Récapitulative Véhicule (impression A4)
import { Component, inject, OnInit, signal, ChangeDetectionStrategy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import {
  VehiculeApiService, CarburantApiService,
  EntretienApiService, SinistreApiService,
  ControleApiService
} from '../../../core/services/api.service';

@Component({
  selector: 'ubi-vehicule-fiche',
  standalone: true,
  imports: [DatePipe, DecimalPipe],
  templateUrl: './vehicule-fiche.component.html',
  styleUrls: ['./vehicule-fiche.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculeFicheComponent implements OnInit {
  private route         = inject(ActivatedRoute);
  router                = inject(Router);       // public pour le template
  private vehiculeApi   = inject(VehiculeApiService);
  private carburantApi  = inject(CarburantApiService);
  private entretienApi  = inject(EntretienApiService);
  private sinistreApi   = inject(SinistreApiService);
  private controleApi   = inject(ControleApiService);

  vehiculeId  = '';
  vehicule    = signal<any>(null);
  loading     = signal(true);
  error       = signal('');
  today       = new Date();

  pleins            = signal<any[]>([]);
  interventions     = signal<any[]>([]);
  contrats          = signal<any[]>([]);
  documents         = signal<any[]>([]);
  relevesKm         = signal<any[]>([]);
  affectations      = signal<any[]>([]);
  historiqueStatuts = signal<any[]>([]);
  ficheControles    = signal<any[]>([]);

  get consommationMoyenne(): number {
    const p = this.pleins().filter((x: any) => x.consommation_calculee);
    if (!p.length) return 0;
    return p.reduce((s: number, x: any) => s + x.consommation_calculee, 0) / p.length;
  }
  get totalDepenseCarburant(): number {
    return this.pleins().reduce((s: number, x: any) => s + (x.montant_fcfa || 0), 0);
  }
  get totalVolume(): number {
    return this.pleins().reduce((s: number, x: any) => s + (x.volume_litres || 0), 0);
  }
  get totalDepenseEntretien(): number {
    return this.interventions().reduce((s: number, x: any) => s + (x.cout_total || 0), 0);
  }
  get numeroFiche(): string {
    const v = this.vehicule();
    if (!v) return '';
    return `FICHE-${v.immatriculation.replace(/[\s-]/g, '')}-${new Date().getFullYear()}`;
  }

  private _loaded = 0;
  private readonly _total = 9;

  ngOnInit(): void {
    this.vehiculeId = this.route.snapshot.paramMap.get('id') ?? '';
    if (!this.vehiculeId) { this.router.navigate(['/vehicules']); return; }
    this.loadAll();
  }

  loadAll(): void {
    this.loading.set(true);
    this._loaded = 0;

    const done = () => { this._loaded++; if (this._loaded >= this._total) this.loading.set(false); };
    const arr  = (r: any) => Array.isArray(r) ? r : (r?.results ?? []);

    this.vehiculeApi.getById(this.vehiculeId).subscribe({
      next: (v: any) => { this.vehicule.set(v); done(); },
      error: () => { this.error.set('Erreur chargement véhicule'); done(); }
    });

    this.carburantApi.getPleins({ vehicule: this.vehiculeId, page_size: 100 }).subscribe({
      next: (r: any) => { this.pleins.set(arr(r)); done(); },
      error: () => done()
    });

    this.entretienApi.getInterventions({ vehicule: this.vehiculeId, page_size: 100 }).subscribe({
      next: (r: any) => { this.interventions.set(arr(r)); done(); },
      error: () => done()
    });

    this.sinistreApi.getContratsByVehicule(this.vehiculeId).subscribe({
      next: (r: any) => { this.contrats.set(arr(r)); done(); },
      error: () => done()
    });

    this.vehiculeApi.getDocuments(this.vehiculeId).subscribe({
      next: (r: any) => { this.documents.set(arr(r)); done(); },
      error: () => done()
    });

    this.vehiculeApi.getRelevesKm({ vehicule: this.vehiculeId, page_size: 50 }).subscribe({
      next: (r: any) => { this.relevesKm.set(arr(r)); done(); },
      error: () => done()
    });

    this.vehiculeApi.getAffectations({ vehicule: this.vehiculeId, page_size: 100 }).subscribe({
      next: (r: any) => { this.affectations.set(arr(r)); done(); },
      error: () => done()
    });

    this.vehiculeApi.getHistoriqueStatuts(this.vehiculeId).subscribe({
      next: (r: any) => { this.historiqueStatuts.set(arr(r)); done(); },
      error: () => done()
    });

    this.controleApi.getFiches({ vehicule: this.vehiculeId, page_size: 20 }).subscribe({
      next: (r: any) => { this.ficheControles.set(arr(r)); done(); },
      error: () => done()
    });
  }

  retour(): void {
    this.router.navigate(['/vehicules', this.vehiculeId]);
  }

  imprimer(): void {
    const v = this.vehicule();
    if (!v) return;
    document.title = `Fiche_${v.immatriculation.replace(/\s/g, '_')}`;
    window.print();
    setTimeout(() => { document.title = 'UbiFleet'; }, 1500);
  }

  statutClass(couleur: string): string {
    const m: Record<string, string> = {
      green: 'badge-green', orange: 'badge-warning',
      red: 'badge-danger', blue: 'badge-blue', gray: 'badge-gray',
    };
    return m[couleur] ?? 'badge-gray';
  }

  statutEntretien(s: string): string {
    const m: Record<string, string> = {
      planifie: 'badge-navy', en_cours: 'badge-info',
      termine: 'badge-green', annule: 'badge-gray', attente_piece: 'badge-warning',
    };
    return m[s] ?? 'badge-gray';
  }

  statutControle(s: string): string {
    const m: Record<string, string> = {
      conforme: 'badge-green', non_conforme: 'badge-danger',
      partiel: 'badge-warning', en_cours: 'badge-gray',
    };
    return m[s] ?? 'badge-gray';
  }
}
