// UbiFleet — Restitution Mensuelle Carburant
import { Component, inject, OnInit, signal, computed, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DecimalPipe, DatePipe } from '@angular/common';
import { VehiculeApiService, AgenceApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';

interface RestitutionRow {
  immatriculation: string;
  marque: string;
  modele: string;
  km_debut: number | null;
  km_fin: number | null;
  distance: number;
  volume_total: number;
  nb_transactions: number;
  conso_100: number | null;
}

@Component({
  selector: 'ubi-restitution-mensuelle',
  standalone: true,
  imports: [RouterLink, DecimalPipe, DatePipe],
  templateUrl: './restitution-mensuelle.component.html',
  styleUrls: ['./restitution-mensuelle.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RestitutionMensuelleComponent implements OnInit {
  private vehiculeApi  = inject(VehiculeApiService);
  private agenceApi    = inject(AgenceApiService);

  agences       = signal<Agence[]>([]);
  dateDebut     = signal('');
  dateFin       = signal('');
  agence        = signal('');
  vehicule      = signal('');
  loading       = signal(false);
  data          = signal<RestitutionRow[]>([]);
  error         = signal('');

  sortKey = signal<string>('immatriculation');
  sortAsc = signal(true);

  // Mois courant par défaut
  private now = new Date();
  private pad = (n: number) => String(n).padStart(2, '0');

  dateSorted = computed(() => {
    const rows = [...this.data()];
    const key  = this.sortKey() as keyof RestitutionRow;
    return rows.sort((a, b) => {
      const va = a[key] ?? -Infinity;
      const vb = b[key] ?? -Infinity;
      return this.sortAsc() ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
  });

  get totalDistance(): number  { return this.data().reduce((s, r) => s + (r.distance || 0), 0); }
  get totalVolume(): number    { return this.data().reduce((s, r) => s + (r.volume_total || 0), 0); }
  get consomoyenne(): number | null {
    const valid = this.data().filter(r => r.conso_100 !== null);
    if (!valid.length) return null;
    return valid.reduce((s, r) => s + (r.conso_100 ?? 0), 0) / valid.length;
  }

  ngOnInit(): void {
    // Valeurs par défaut : mois courant
    const y = this.now.getFullYear();
    const m = this.now.getMonth() + 1;
    this.dateDebut.set(`${y}-${this.pad(m)}-01`);
    this.dateFin.set(`${y}-${this.pad(m)}-${new Date(y, m, 0).getDate()}`);

    this.agenceApi.getAll().subscribe({
      next: (r) => this.agences.set(r),
      error: () => {},
    });
  }

  calculer(): void {
    if (!this.dateDebut() || !this.dateFin()) {
      this.error.set('Veuillez sélectionner une période.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.vehiculeApi.getConsommationKm({
      date_debut: this.dateDebut(),
      date_fin:   this.dateFin(),
      agence:     this.agence()   || undefined,
      vehicule:   this.vehicule() || undefined,
    }).subscribe({
      next: (r: any) => {
        const rows: RestitutionRow[] = (Array.isArray(r) ? r : r.resultats ?? []).map((x: any) => ({
          immatriculation: x.immatriculation,
          marque:          x.marque  ?? '',
          modele:          x.modele  ?? '',
          km_debut:        x.km_debut ?? null,
          km_fin:          x.km_fin   ?? null,
          distance:        x.distance ?? 0,
          volume_total:    x.volume_total ?? 0,
          nb_transactions: x.nb_transactions ?? 0,
          conso_100:       x.conso_100 ?? null,
        }));
        this.data.set(rows);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Erreur lors du calcul.');
        this.loading.set(false);
      },
    });
  }

  sort(key: string): void {
    if (this.sortKey() === key) this.sortAsc.set(!this.sortAsc());
    else { this.sortKey.set(key); this.sortAsc.set(true); }
  }

  consoBadge(v: number): string {
    if (v > 25) return 'badge-danger';
    if (v > 18) return 'badge-warning';
    return 'badge-green';
  }

  exportCsv(): void {
    const sep = ';'; const eol = '\r\n';
    const hdrs = ['Immatriculation','Marque/Modèle','Km début','Km fin',
                  'Distance (km)','Volume (L)','Nb trans.','Conso L/100'].join(sep);
    const data = this.dateSorted().map(r => [
      r.immatriculation, `${r.marque} ${r.modele}`.trim(),
      r.km_debut ?? '', r.km_fin ?? '', r.distance, r.volume_total,
      r.nb_transactions, r.conso_100 ?? 'N/A',
    ].join(sep)).join(eol);
    const blob = new Blob(['\uFEFF' + hdrs + eol + data], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `restitution_${this.dateDebut()}_${this.dateFin()}.csv`;
    a.click(); URL.revokeObjectURL(url);
  }
}
