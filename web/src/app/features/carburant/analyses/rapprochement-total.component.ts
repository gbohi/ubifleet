// UbiFleet — Carburant › Rapprochement Total (déclaré vs facturé)
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { CarburantApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { Agence } from '../../../core/models';
import { FiltresAnalyse, FiltresAnalyseComponent, exporterCsv } from './filtres-analyse.component';

type Vue = 'synthese' | 'transaction_sans_prise' | 'prise_sans_transaction' | 'ecart' | 'rapproche' | 'inconnues';

const STATUTS: Record<string, { libelle: string; classe: string }> = {
  rapproche: { libelle: 'Rapprochée', classe: 'badge-green' },
  ecart: { libelle: 'Écart', classe: 'badge-warning' },
  transaction_sans_prise: { libelle: 'Facturée sans prise', classe: 'badge-danger' },
  prise_sans_transaction: { libelle: 'Prise sans facture', classe: 'badge-info' },
};

@Component({
  selector: 'ubi-rapprochement-total',
  standalone: true,
  imports: [DecimalPipe, DatePipe, RouterLink, FiltresAnalyseComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./analyses.scss'],
  template: `
    <div class="an-entete">
      <h2><i class="fas fa-balance-scale"></i> Rapprochement TotalEnergies</h2>
      <p>Les prises déclarées dans UbiFleet sont comparées aux transactions facturées par Total (ventes non annulées).
        Une transaction est associée au véhicule par sa carte carburant (fiche véhicule), sinon par la plaque ; puis à la prise
        la plus proche (écart d'heure ≤ {{ param()?.tolerance_heures ?? '…' }} h, volume proche).
        Écart signalé au-delà de {{ param()?.ecart_pct ?? '…' }} % de volume ou de montant (Paramètres › Seuils).</p>
    </div>
    <ubi-filtres-analyse [agences]="agences()" [avecType]="false" [chargement]="chargement()" (appliquer)="charger($event)">
      <button class="btn btn-outline" [disabled]="!donnees()" (click)="exporter()"><i class="fas fa-file-excel"></i> Exporter</button>
    </ubi-filtres-analyse>
    @if (erreur()) { <div class="an-notice"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }

    @if (donnees(); as d) {
      <div class="an-kpis">
        <div class="an-kpi"><span class="an-kpi-lbl">Litres déclarés / facturés</span>
          <span class="an-kpi-val">{{ d.totaux.litres_declares | number:'1.0-0' }} / {{ d.totaux.litres_factures | number:'1.0-0' }}</span>
          <span class="an-kpi-sub">écart {{ signe(d.totaux.ecart_litres) }}{{ d.totaux.ecart_litres | number:'1.0-1' }} L</span></div>
        <div class="an-kpi"><span class="an-kpi-lbl">Montant facturé par Total</span>
          <span class="an-kpi-val">{{ d.totaux.montant_facture | number:'1.0-0' }} F</span>
          <span class="an-kpi-sub">déclaré {{ d.totaux.montant_declare | number:'1.0-0' }} · écart {{ signe(d.totaux.ecart_montant) }}{{ d.totaux.ecart_montant | number:'1.0-0' }} F</span></div>
        <div class="an-kpi" [class.alerte]="d.totaux.nb_transactions_sans_prise > 0">
          <span class="an-kpi-lbl">Facturées sans prise</span><span class="an-kpi-val">{{ d.totaux.nb_transactions_sans_prise }}</span>
          <span class="an-kpi-sub">carte utilisée sans saisie dans UbiFleet</span></div>
        <div class="an-kpi" [class.attention]="d.totaux.nb_ecarts > 0">
          <span class="an-kpi-lbl">Rapprochées / écarts</span>
          <span class="an-kpi-val">{{ d.totaux.nb_rapproches }} / {{ d.totaux.nb_ecarts }}</span>
          <span class="an-kpi-sub">{{ d.totaux.nb_prises_sans_transaction }} prise(s) sans facture Total</span></div>
      </div>

      <div class="an-onglets" role="tablist">
        <button [class.active]="vue() === 'synthese'" (click)="vue.set('synthese')">Par véhicule <span class="an-nb">{{ d.synthese.length }}</span></button>
        <button [class.active]="vue() === 'transaction_sans_prise'" (click)="vue.set('transaction_sans_prise')">Facturées sans prise <span class="an-nb">{{ compte('transaction_sans_prise') }}</span></button>
        <button [class.active]="vue() === 'ecart'" (click)="vue.set('ecart')">Écarts <span class="an-nb">{{ compte('ecart') }}</span></button>
        <button [class.active]="vue() === 'prise_sans_transaction'" (click)="vue.set('prise_sans_transaction')">Prises sans facture <span class="an-nb">{{ compte('prise_sans_transaction') }}</span></button>
        <button [class.active]="vue() === 'rapproche'" (click)="vue.set('rapproche')">Rapprochées <span class="an-nb">{{ compte('rapproche') }}</span></button>
        <button [class.active]="vue() === 'inconnues'" (click)="vue.set('inconnues')">Plaques Total inconnues <span class="an-nb">{{ d.immatriculations_inconnues.length }}</span></button>
      </div>

      @switch (vue()) {
        @case ('synthese') {
          @if (!d.synthese.length) { <div class="an-vide">Aucune prise ni transaction sur la période.</div> }
          @else {
            <div class="an-table-wrap"><table class="an-table">
              <thead><tr><th>Véhicule</th><th class="num">Prises</th><th class="num">Transactions</th>
                <th class="num">Litres déclarés</th><th class="num">Litres facturés</th><th class="num">Écart L</th>
                <th class="num">Montant déclaré</th><th class="num">Montant facturé</th><th class="num">Écart F</th>
                <th class="num">Sans prise</th><th class="num">Sans facture</th><th class="num">Écarts</th>
                <th class="num">Conso UbiFleet</th><th class="num">Conso Total</th></tr></thead>
              <tbody>
                @for (s of d.synthese; track s.vehicule_id) {
                  <tr>
                    <td class="nowrap"><span class="fort">{{ s.immatriculation }}</span>
                      @if (!s.carte) { <span class="muted petit" title="Carte carburant non renseignée sur la fiche véhicule : rapprochement par la plaque"> · plaque</span> }</td>
                    <td class="num">{{ s.nb_prises }}</td><td class="num">{{ s.nb_transactions }}</td>
                    <td class="num">{{ s.litres_declares | number:'1.0-2' }}</td><td class="num">{{ s.litres_factures | number:'1.0-2' }}</td>
                    <td class="num" [class.ecart-pos]="s.ecart_litres < -0.5" [class.ecart-neg]="s.ecart_litres > 0.5">{{ signe(s.ecart_litres) }}{{ s.ecart_litres | number:'1.0-2' }}</td>
                    <td class="num">{{ s.montant_declare | number:'1.0-0' }}</td><td class="num">{{ s.montant_facture | number:'1.0-0' }}</td>
                    <td class="num" [class.ecart-pos]="s.ecart_montant < -1">{{ signe(s.ecart_montant) }}{{ s.ecart_montant | number:'1.0-0' }}</td>
                    <td class="num" [class.ecart-pos]="s.nb_transactions_sans_prise > 0">{{ s.nb_transactions_sans_prise }}</td>
                    <td class="num">{{ s.nb_prises_sans_transaction }}</td>
                    <td class="num">{{ s.nb_ecarts }}</td>
                    <td class="num">{{ s.conso_ubifleet ?? '—' }}</td>
                    <td class="num">{{ s.conso_total ?? '—' }}</td>
                  </tr>
                }
              </tbody>
              <tfoot><tr><td>Total</td><td></td><td></td>
                <td class="num">{{ d.totaux.litres_declares | number:'1.0-0' }}</td><td class="num">{{ d.totaux.litres_factures | number:'1.0-0' }}</td>
                <td class="num">{{ signe(d.totaux.ecart_litres) }}{{ d.totaux.ecart_litres | number:'1.0-1' }}</td>
                <td class="num">{{ d.totaux.montant_declare | number:'1.0-0' }}</td><td class="num">{{ d.totaux.montant_facture | number:'1.0-0' }}</td>
                <td class="num">{{ signe(d.totaux.ecart_montant) }}{{ d.totaux.ecart_montant | number:'1.0-0' }}</td>
                <td class="num">{{ d.totaux.nb_transactions_sans_prise }}</td><td class="num">{{ d.totaux.nb_prises_sans_transaction }}</td>
                <td class="num">{{ d.totaux.nb_ecarts }}</td><td></td><td></td></tr></tfoot>
            </table></div>
            <p class="an-note">Écart = déclaré − facturé (négatif : Total facture plus que ce qui est déclaré). Conso Total : mêmes règles
              que UbiFleet, en ignorant les kilométrages saisis à la pompe nuls ou qui reculent.</p>
          }
        }
        @case ('inconnues') {
          @if (!d.immatriculations_inconnues.length) { <div class="an-vide">Toutes les transactions sont rattachées à un véhicule.</div> }
          @else {
            <div class="an-notice info"><i class="fas fa-info-circle"></i>
              Transactions Total dont la carte et la plaque ne correspondent à aucun véhicule de la base. Renseignez la carte carburant
              sur la fiche du véhicule concerné pour les rattacher.</div>
            <div class="an-table-wrap"><table class="an-table">
              <thead><tr><th>Plaque saisie chez Total</th><th class="num">Transactions</th><th class="num">Litres</th><th class="num">Montant</th></tr></thead>
              <tbody>
                @for (i of d.immatriculations_inconnues; track i.immatriculation) {
                  <tr><td class="fort">{{ i.immatriculation }}</td><td class="num">{{ i.nb }}</td>
                    <td class="num">{{ i.volume | number:'1.0-2' }}</td><td class="num">{{ i.montant | number:'1.0-0' }}</td></tr>
                }
              </tbody>
            </table></div>
          }
        }
        @default {
          @if (!lignesVue().length) { <div class="an-vide">Aucune ligne.</div> }
          @else {
            <div class="an-table-wrap"><table class="an-table">
              <thead><tr><th>Véhicule</th><th>Statut</th>
                <th>Prise UbiFleet</th><th class="num">Litres</th><th class="num">Montant</th><th>Chauffeur</th>
                <th>Transaction Total</th><th class="num">Litres</th><th class="num">Montant</th><th>Station Total</th><th>Chauffeur Total</th>
                <th class="num">Écart vol.</th><th class="num">Écart mont.</th><th></th></tr></thead>
              <tbody>
                @for (l of lignesVue(); track $index) {
                  <tr>
                    <td class="nowrap fort">{{ l.immatriculation }}</td>
                    <td><span class="badge" [class]="statut(l.statut).classe">{{ statut(l.statut).libelle }}</span>
                      @if (l.chauffeur_different) { <span class="badge badge-warning" title="Le chauffeur de la prise n'est pas celui de la transaction Total">Chauffeur ≠</span> }</td>
                    <td class="nowrap">@if (l.prise_date) { {{ l.prise_date | date:'dd/MM/yyyy' }} {{ (l.prise_heure ?? '').substring(0, 5) }} } @else { <span class="muted">—</span> }</td>
                    <td class="num">{{ l.prise_volume ?? '' }}</td><td class="num">{{ l.prise_montant === null ? '' : (l.prise_montant | number:'1.0-0') }}</td>
                    <td>{{ l.prise_chauffeur ?? '' }}</td>
                    <td class="nowrap">@if (l.transaction_date) { {{ l.transaction_date | date:'dd/MM/yyyy' }} {{ (l.transaction_heure ?? '').substring(0, 5) }}
                      <span class="muted petit">n° {{ l.transaction_ticket }}</span> } @else { <span class="muted">—</span> }</td>
                    <td class="num">{{ l.transaction_volume ?? '' }}</td><td class="num">{{ l.transaction_montant === null ? '' : (l.transaction_montant | number:'1.0-0') }}</td>
                    <td>{{ l.transaction_station ?? '' }}</td><td>{{ l.transaction_chauffeur ?? '' }}</td>
                    <td class="num" [class.ecart-pos]="l.statut === 'ecart'">{{ l.ecart_volume_pct === null ? '' : l.ecart_volume_pct + ' %' }}</td>
                    <td class="num" [class.ecart-pos]="l.statut === 'ecart'">{{ l.ecart_montant_pct === null ? '' : l.ecart_montant_pct + ' %' }}</td>
                    <td>@if (l.prise_id) { <a [routerLink]="['/carburant', l.prise_id, 'modifier']" title="Ouvrir la prise"><i class="fas fa-external-link-alt"></i></a> }</td>
                  </tr>
                }
              </tbody>
            </table></div>
          }
        }
      }
    }
  `,
})
export class RapprochementTotalComponent {
  agences = input<Agence[]>([]);
  private api = inject(CarburantApiService);

  donnees = signal<any | null>(null);
  vue = signal<Vue>('synthese');
  chargement = signal(false);
  erreur = signal('');
  private filtres: FiltresAnalyse | null = null;

  param = computed(() => this.donnees()?.parametres);
  lignesVue = computed(() => (this.donnees()?.lignes ?? []).filter((l: any) => l.statut === this.vue()));

  compte(statut: string): number { return (this.donnees()?.lignes ?? []).filter((l: any) => l.statut === statut).length; }
  statut(s: string) { return STATUTS[s] ?? { libelle: s, classe: 'badge-gray' }; }
  signe(v: number | null): string { return v !== null && v > 0 ? '+' : ''; }

  charger(f: FiltresAnalyse): void {
    this.filtres = f;
    this.chargement.set(true);
    this.erreur.set('');
    this.api.getRapprochementTotal(f).subscribe({
      next: (r: any) => { this.donnees.set(r); this.chargement.set(false); },
      error: (err) => { this.erreur.set(messageErreurApi(err, 'Erreur lors du rapprochement.')); this.chargement.set(false); },
    });
  }

  exporter(): void {
    const d = this.donnees();
    if (!d) return;
    const periode = `${this.filtres?.date_debut}_${this.filtres?.date_fin}`;
    if (this.vue() === 'synthese' || this.vue() === 'inconnues') {
      exporterCsv(`rapprochement_total_vehicules_${periode}.csv`,
        ['Véhicule', 'Prises', 'Transactions', 'Litres déclarés', 'Litres facturés', 'Écart L', 'Montant déclaré',
         'Montant facturé', 'Écart FCFA', 'Facturées sans prise', 'Prises sans facture', 'Écarts', 'Conso UbiFleet', 'Conso Total'],
        d.synthese.map((s: any) => [s.immatriculation, s.nb_prises, s.nb_transactions, s.litres_declares, s.litres_factures,
          s.ecart_litres, s.montant_declare, s.montant_facture, s.ecart_montant, s.nb_transactions_sans_prise,
          s.nb_prises_sans_transaction, s.nb_ecarts, s.conso_ubifleet, s.conso_total]));
      return;
    }
    exporterCsv(`rapprochement_total_lignes_${periode}.csv`,
      ['Véhicule', 'Statut', 'Date prise', 'Heure prise', 'Litres prise', 'Montant prise', 'Chauffeur prise',
       'Date transaction', 'Heure transaction', 'Ticket', 'Litres transaction', 'Montant transaction', 'Station Total',
       'Chauffeur Total', 'Écart volume %', 'Écart montant %', 'Chauffeur différent'],
      d.lignes.map((l: any) => [l.immatriculation, this.statut(l.statut).libelle, l.prise_date, (l.prise_heure ?? '').slice(0, 5),
        l.prise_volume, l.prise_montant, l.prise_chauffeur, l.transaction_date, (l.transaction_heure ?? '').slice(0, 5),
        l.transaction_ticket, l.transaction_volume, l.transaction_montant, l.transaction_station, l.transaction_chauffeur,
        l.ecart_volume_pct, l.ecart_montant_pct, l.chauffeur_different ? 'oui' : '']));
  }
}
