// UbiFleet — Restitution Mensuelle Carburant : consommation facturée par
// véhicule sur le mois (même calcul que l'onglet Consommation des relevés km).
import { Component, inject, OnInit, signal, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AgenceApiService } from '../../../core/services/api.service';
import { Agence } from '../../../core/models';
import { ConsommationFactureeComponent } from '../analyses/consommation-facturee.component';

@Component({
  selector: 'ubi-restitution-mensuelle',
  standalone: true,
  imports: [RouterLink, ConsommationFactureeComponent],
  templateUrl: './restitution-mensuelle.component.html',
  styleUrls: ['./restitution-mensuelle.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RestitutionMensuelleComponent implements OnInit {
  private agenceApi = inject(AgenceApiService);
  agences = signal<Agence[]>([]);

  ngOnInit(): void {
    this.agenceApi.getAll().subscribe({
      next: (r: any) => this.agences.set(Array.isArray(r) ? r : (r?.results ?? [])),
      error: () => {},
    });
  }

  imprimer(): void { window.print(); }
}
