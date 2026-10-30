// UbiFleet — Carburant › Consommation (par véhicule, méthode plein à plein)
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { CarburantApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { Agence } from '../../../core/models';
import { InfoOngletComponent } from '../../../shared/info-onglet/info-onglet.component';
import { FiltresAnalyse, FiltresAnalyseComponent, exporterCsv } from './filtres-analyse.component';

@Component({
  selector: 'ubi-consommation-vehicules',
  standalone: true,
  imports: [DecimalPipe, DatePipe, FiltresAnalyseComponent, InfoOngletComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./analyses.scss'],
  template: `
    <ubi-info-onglet titre="Consommation par véhicule" icone="fas fa-tachometer-alt">
      Méthode « plein à plein » : chaque prise couvre les km parcourus depuis la prise précédente du véhicule.
        Conso moyenne = litres ÷ km × 100 sur la période, comparée à la consommation théorique de référence de la fiche véhicule.
        Avec un filtre chauffeur ou type, seuls les intervalles de ses prises sont comptés.
    </ubi-info-onglet>
    <ubi-filtres-analyse [agences]="agences()" [chargement]="chargement()" (appliquer)="charger($event)">
      <button class="btn btn-outline" [disabled]="!lignes().length" (click)="exporter()"><i class="fas fa-file-excel"></i> Exporter</button>
    </ubi-filtres-analyse>
    @if (erreur()) { <div class="an-notice"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }

    @if (lignes().length) {
      <div class="an-kpis">
        <div class="an-kpi"><span class="an-kpi-lbl">Véhicules</span><span class="an-kpi-val">{{ lignes().length }}</span>
          <span class="an-kpi-sub">{{ synthese().insuffisants }} sans historique suffisant</span></div>
        <div class="an-kpi"><span class="an-kpi-lbl">Litres / km</span><span class="an-kpi-val">{{ synthese().litres | number:'1.0-0' }} L</span>
          <span class="an-kpi-sub">{{ synthese().km | number:'1.0-0' }} km · {{ synthese().montant | number:'1.0-0' }} F</span></div>
        <div class="an-kpi"><span class="an-kpi-lbl">Conso moyenne du parc</span>
          <span class="an-kpi-val">{{ synthese().conso === null ? '—' : (synthese().conso | number:'1.1-2') + ' L/100' }}</span>
          <span class="an-kpi-sub">pondérée par les km</span></div>
        <div class="an-kpi" [class.alerte]="synthese().depassements > 0">
          <span class="an-kpi-lbl">Au-dessus de la référence</span><span class="an-kpi-val">{{ synthese().depassements }}</span>
          <span class="an-kpi-sub">véhicule(s) à plus de 10 % de la référence</span></div>
      </div>
      <div class="an-table-wrap">
        <table class="an-table">
          <thead><tr>
            <th class="triable" (click)="trier('immatriculation')">Véhicule</th><th>Type</th>
            <th class="num triable" (click)="trier('nb_prises')">Prises</th>
            <th class="num triable" (click)="trier('km_parcourus')">Km</th>
            <th class="num triable" (click)="trier('litres')">Litres</th>
            <th class="num triable" (click)="trier('montant')">Montant</th>
            <th class="num triable" (click)="trier('conso_moyenne')">Conso moy. L/100</th>
            <th class="num">Référence</th>
            <th class="num triable" (click)="trier('ecart_pct')">Écart</th>
            <th class="num triable" (click)="trier('derniere_conso')">Dernière conso</th>
            <th class="num triable" (click)="trier('nb_anomalies')">Anomalies</th>
            <th class="num triable" (click)="trier('part_hors_tournee')">Hors tournée</th>
          </tr></thead>
          <tbody>
            @for (l of triees(); track l.vehicule_id) {
              <tr>
                <td class="nowrap"><span class="fort">{{ l.immatriculation }}</span>
                  <div class="muted petit">{{ l.marque }} {{ l.modele }}</div></td>
                <td>{{ l.type_vehicule }}</td>
                <td class="num">{{ l.nb_prises }}</td>
                <td class="num">{{ l.km_parcourus === null ? '—' : (l.km_parcourus | number:'1.0-0') }}</td>
                <td class="num">{{ l.litres | number:'1.0-2' }}</td>
                <td class="num">{{ l.montant | number:'1.0-0' }}</td>
                <td class="num fort">
                  @if (l.historique_insuffisant) { <span class="muted" title="Il faut au moins deux prises du véhicule pour calculer une consommation">historique insuffisant</span> }
                  @else { {{ l.conso_moyenne ?? '—' }} }
                </td>
                <td class="num">{{ l.conso_reference ?? '' }}@if (!l.conso_reference) { <span class="muted petit" title="Renseignez la consommation théorique de référence sur la fiche véhicule">non renseignée</span> }</td>
                <td class="num" [class.ecart-pos]="(l.ecart_pct ?? 0) > 10" [class.ecart-neg]="(l.ecart_pct ?? 0) < -10">
                  {{ l.ecart_pct === null ? '—' : (l.ecart_pct > 0 ? '+' : '') + l.ecart_pct + ' %' }}</td>
                <td class="num">{{ l.derniere_conso ?? '—' }}<div class="muted petit">{{ l.derniere_date | date:'dd/MM' }}</div></td>
                <td class="num" [class.ecart-pos]="l.nb_anomalies > 0">{{ l.nb_anomalies }}</td>
                <td class="num">{{ l.part_hors_tournee === null ? '—' : l.part_hors_tournee + ' %' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <p class="an-note">Écart = conso moyenne de la période par rapport à la consommation théorique de référence (en rouge au-delà de +10 %).
        Dernière conso = dernière prise de la période, sensible à un plein partiel.</p>
    } @else if (!chargement()) {
      <div class="an-vide"><i class="fas fa-tachometer-alt"></i> Aucune prise de carburant sur la période.</div>
    }
  `,
})
export class ConsommationVehiculesComponent {
  agences = input<Agence[]>([]);
  private api = inject(CarburantApiService);

  lignes = signal<any[]>([]);
  chargement = signal(false);
  erreur = signal('');
  private filtres: FiltresAnalyse | null = null;
  tri = signal<{ cle: string; asc: boolean }>({ cle: 'ecart_pct', asc: false });

  triees = computed(() => {
    const { cle, asc } = this.tri();
    const val = (l: any) => l[cle] ?? (asc ? Infinity : -Infinity);
    return [...this.lignes()].sort((a, b) => {
      const va = val(a), vb = val(b);
      const c = typeof va === 'string' ? va.localeCompare(vb) : va - vb;
      return asc ? c : -c;
    });
  });

  synthese = computed(() => {
    const l = this.lignes();
    const km = l.reduce((a, x) => a + (x.km_parcourus ?? 0), 0);
    // Litres des intervalles comptés : conso × km de chaque véhicule
    const litresKm = l.reduce((a, x) => a + (x.conso_moyenne !== null ? x.conso_moyenne * (x.km_parcourus ?? 0) / 100 : 0), 0);
    return {
      litres: l.reduce((a, x) => a + x.litres, 0), montant: l.reduce((a, x) => a + x.montant, 0), km,
      conso: km ? litresKm / km * 100 : null,
      insuffisants: l.filter(x => x.historique_insuffisant).length,
      depassements: l.filter(x => (x.ecart_pct ?? 0) > 10).length,
    };
  });

  charger(f: FiltresAnalyse): void {
    this.filtres = f;
    this.chargement.set(true);
    this.erreur.set('');
    this.api.getConsommation(f).subscribe({
      next: (r: any) => { this.lignes.set(r.resultats ?? []); this.chargement.set(false); },
      error: (err) => { this.erreur.set(messageErreurApi(err, 'Erreur lors du calcul.')); this.chargement.set(false); },
    });
  }

  trier(cle: string): void {
    const t = this.tri();
    this.tri.set({ cle, asc: t.cle === cle ? !t.asc : cle === 'immatriculation' });
  }

  exporter(): void {
    exporterCsv(`consommation_${this.filtres?.date_debut}_${this.filtres?.date_fin}.csv`,
      ['Véhicule', 'Marque', 'Modèle', 'Type', 'Prises', 'Km', 'Litres', 'Montant (FCFA)', 'Conso moyenne L/100',
       'Conso de référence', 'Écart L/100', 'Écart %', 'Dernière conso', 'Date dernière prise', 'Anomalies', 'Part hors tournée %'],
      this.triees().map(l => [l.immatriculation, l.marque, l.modele, l.type_vehicule, l.nb_prises, l.km_parcourus, l.litres,
        l.montant, l.conso_moyenne, l.conso_reference, l.ecart_100, l.ecart_pct, l.derniere_conso, l.derniere_date,
        l.nb_anomalies, l.part_hors_tournee]));
  }
}
