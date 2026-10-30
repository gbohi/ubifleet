// UbiFleet — Consommation facturée : litres TotalEnergies ÷ km du compteur
// UbiFleet (onglet Consommation des relevés km, page Restitution mensuelle).
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { VehiculeApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { Agence } from '../../../core/models';
import { InfoOngletComponent } from '../../../shared/info-onglet/info-onglet.component';
import { FiltresAnalyse, FiltresAnalyseComponent, exporterCsv } from './filtres-analyse.component';

@Component({
  selector: 'ubi-consommation-facturee',
  standalone: true,
  imports: [DecimalPipe, FiltresAnalyseComponent, InfoOngletComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./analyses.scss'],
  template: `
    <ubi-info-onglet [titre]="titre()" icone="fas fa-file-invoice">
      Consommation <strong>facturée</strong> : litres facturés par TotalEnergies (ventes non annulées, rattachées au véhicule
      par sa carte carburant, sinon par la plaque) rapportés aux km du compteur UbiFleet (relevés et prises de carburant)
      entre la première et la dernière transaction de la période. Les litres de la première transaction sont exclus :
      ils ont servi aux km d'avant (méthode plein à plein). Le compteur à l'heure d'une transaction est estimé entre la
      saisie d'avant et celle d'après. Elle est comparée à la consommation déclarée (prises UbiFleet) et à la
      consommation théorique de référence de la fiche véhicule.
    </ubi-info-onglet>
    <ubi-filtres-analyse [agences]="agences()" [avecType]="false" [moisPrecedents]="moisPrecedents()"
                         [chargement]="chargement()" (appliquer)="charger($event)">
      <button class="btn btn-outline" [disabled]="!lignes().length" (click)="exporter()"><i class="fas fa-file-excel"></i> Exporter</button>
    </ubi-filtres-analyse>
    @if (erreur()) { <div class="an-notice"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }

    @if (lignes().length) {
      <div class="an-kpis">
        <div class="an-kpi"><span class="an-kpi-lbl">Litres facturés</span><span class="an-kpi-val">{{ synthese().litres | number:'1.0-0' }} L</span>
          <span class="an-kpi-sub">{{ synthese().transactions }} transaction(s) · déclarés {{ synthese().declares | number:'1.0-0' }} L</span></div>
        <div class="an-kpi"><span class="an-kpi-lbl">Conso facturée du parc</span>
          <span class="an-kpi-val">{{ synthese().conso === null ? '—' : (synthese().conso | number:'1.1-2') + ' L/100' }}</span>
          <span class="an-kpi-sub">{{ synthese().km | number:'1.0-0' }} km mesurés par UbiFleet</span></div>
        <div class="an-kpi" [class.alerte]="synthese().depassements > 0"><span class="an-kpi-lbl">Au-dessus de la référence</span>
          <span class="an-kpi-val">{{ synthese().depassements }}</span><span class="an-kpi-sub">véhicule(s) à plus de 10 %</span></div>
        <div class="an-kpi" [class.attention]="synthese().ecartsDeclares > 0"><span class="an-kpi-lbl">Facturé ≠ déclaré</span>
          <span class="an-kpi-val">{{ synthese().ecartsDeclares }}</span><span class="an-kpi-sub">véhicule(s) à plus de 10 % d'écart</span></div>
      </div>
      <div class="an-table-wrap">
        <table class="an-table">
          <thead><tr>
            <th class="triable" (click)="trier('immatriculation')">Véhicule</th>
            <th class="num triable" (click)="trier('nb_transactions')">Transactions</th>
            <th class="num triable" (click)="trier('litres_factures')">Litres facturés</th>
            <th class="num">Km début</th><th class="num">Km fin</th>
            <th class="num triable" (click)="trier('km_parcourus')">Km parcourus</th>
            <th class="num triable" (click)="trier('conso_facturee')">Conso facturée</th>
            <th class="num triable" (click)="trier('conso_declaree')">Conso déclarée</th>
            <th class="num">Référence</th>
            <th class="num triable" (click)="trier('ecart_reference_pct')">Écart / référence</th>
            <th class="num triable" (click)="trier('ecart_declaree_pct')">Écart / déclarée</th>
          </tr></thead>
          <tbody>
            @for (l of triees(); track l.vehicule_id) {
              <tr>
                <td class="nowrap"><span class="fort">{{ l.immatriculation }}</span>
                  @if (!l.carte) { <span class="muted petit" title="Carte carburant non renseignée : transactions rattachées par la plaque"> · plaque</span> }
                  <div class="muted petit">{{ l.marque }} {{ l.modele }}</div></td>
                <td class="num">{{ l.nb_transactions }}</td>
                <td class="num">{{ l.litres_factures | number:'1.0-2' }}</td>
                <td class="num">{{ l.km_debut === null ? '—' : (l.km_debut | number:'1.0-0') }}</td>
                <td class="num">{{ l.km_fin === null ? '—' : (l.km_fin | number:'1.0-0') }}</td>
                <td class="num">{{ l.km_parcourus === null ? '—' : (l.km_parcourus | number:'1.0-0') }}</td>
                <td class="num fort">
                  @if (l.conso_facturee !== null) { {{ l.conso_facturee }} } @else { <span class="muted petit">{{ l.motif }}</span> }
                </td>
                <td class="num">{{ l.conso_declaree ?? '—' }}</td>
                <td class="num">@if (l.conso_reference) { {{ l.conso_reference }} } @else { <span class="muted petit" title="Renseignez la consommation théorique de référence sur la fiche véhicule">non renseignée</span> }</td>
                <td class="num" [class.ecart-pos]="(l.ecart_reference_pct ?? 0) > 10" [class.ecart-neg]="(l.ecart_reference_pct ?? 0) < -10">{{ pct(l.ecart_reference_pct) }}</td>
                <td class="num" [class.ecart-pos]="(l.ecart_declaree_pct ?? 0) > 10" [class.ecart-neg]="(l.ecart_declaree_pct ?? 0) < -10">{{ pct(l.ecart_declaree_pct) }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <p class="an-note">En rouge : plus de 10 % au-dessus de la référence, ou facturé nettement supérieur au déclaré
        (carburant acheté sans être déclaré, ou kilométrage sous-déclaré).</p>
    } @else if (!chargement()) {
      <div class="an-vide"><i class="fas fa-file-invoice"></i> Aucune transaction ni prise sur la période.</div>
    }

    @if (inconnues().length) {
      <details class="cf-inconnues">
        <summary>{{ inconnues().length }} plaque(s) Total non rattachée(s) à un véhicule
          ({{ litresInconnus() | number:'1.0-0' }} L) — renseignez la carte carburant sur la fiche véhicule</summary>
        <div class="an-table-wrap"><table class="an-table">
          <thead><tr><th>Plaque chez Total</th><th class="num">Transactions</th><th class="num">Litres</th><th class="num">Montant</th></tr></thead>
          <tbody>
            @for (i of inconnues(); track i.immatriculation) {
              <tr><td class="fort">{{ i.immatriculation }}</td><td class="num">{{ i.nb }}</td>
                <td class="num">{{ i.volume | number:'1.0-2' }}</td><td class="num">{{ i.montant | number:'1.0-0' }}</td></tr>
            }
          </tbody>
        </table></div>
      </details>
    }
  `,
  styles: [`
    .cf-inconnues { margin-top: 14px; font-size: 12.5px;
      summary { cursor: pointer; color: var(--gray-500); margin-bottom: 8px; } }
  `],
})
export class ConsommationFactureeComponent {
  agences = input<Agence[]>([]);
  titre = input('Consommation facturée (Total)');
  moisPrecedents = input(2);
  private api = inject(VehiculeApiService);

  lignes = signal<any[]>([]);
  inconnues = signal<any[]>([]);
  chargement = signal(false);
  erreur = signal('');
  private filtres: FiltresAnalyse | null = null;
  private requete = 0;
  tri = signal<{ cle: string; asc: boolean }>({ cle: 'ecart_reference_pct', asc: false });

  triees = computed(() => {
    const { cle, asc } = this.tri();
    const val = (l: any) => l[cle] ?? (asc ? Infinity : -Infinity);
    return [...this.lignes()].sort((a, b) => {
      const va = val(a), vb = val(b);
      const c = typeof va === 'string' ? va.localeCompare(vb) : va - vb;
      return asc ? c : -c;
    });
  });
  litresInconnus = computed(() => this.inconnues().reduce((a, i) => a + i.volume, 0));

  synthese = computed(() => {
    const l = this.lignes();
    const avecConso = l.filter(x => x.conso_facturee !== null);
    const km = avecConso.reduce((a, x) => a + x.km_parcourus, 0);
    const litresKm = avecConso.reduce((a, x) => a + x.conso_facturee * x.km_parcourus / 100, 0);
    return {
      litres: l.reduce((a, x) => a + x.litres_factures, 0), declares: l.reduce((a, x) => a + x.litres_declares, 0),
      transactions: l.reduce((a, x) => a + x.nb_transactions, 0), km,
      conso: km ? litresKm / km * 100 : null,
      depassements: l.filter(x => (x.ecart_reference_pct ?? 0) > 10).length,
      ecartsDeclares: l.filter(x => Math.abs(x.ecart_declaree_pct ?? 0) > 10).length,
    };
  });

  pct(v: number | null): string { return v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${v} %`; }

  trier(cle: string): void {
    const t = this.tri();
    this.tri.set({ cle, asc: t.cle === cle ? !t.asc : cle === 'immatriculation' });
  }

  charger(f: FiltresAnalyse): void {
    this.filtres = f;
    this.chargement.set(true);
    this.erreur.set('');
    const n = ++this.requete;   // seule la dernière demande s'affiche
    this.api.getConsommationKm(f).subscribe({
      next: (r: any) => {
        if (n !== this.requete) return;
        this.lignes.set(r.resultats ?? []);
        this.inconnues.set(r.immatriculations_inconnues ?? []);
        this.chargement.set(false);
      },
      error: (err) => {
        if (n !== this.requete) return; this.erreur.set(messageErreurApi(err, 'Erreur lors du calcul.')); this.chargement.set(false); },
    });
  }

  exporter(): void {
    exporterCsv(`consommation_facturee_${this.filtres?.date_debut}_${this.filtres?.date_fin}.csv`,
      ['Véhicule', 'Marque', 'Modèle', 'Agence', 'Transactions Total', 'Litres facturés', 'Montant facturé (FCFA)',
       'Km début', 'Km fin', 'Km parcourus', 'Conso facturée L/100', 'Prises déclarées', 'Litres déclarés',
       'Conso déclarée L/100', 'Conso de référence', 'Écart / référence %', 'Écart / déclarée %', 'Remarque'],
      this.triees().map(l => [l.immatriculation, l.marque, l.modele, l.agence_nom, l.nb_transactions, l.litres_factures,
        l.montant_facture, l.km_debut, l.km_fin, l.km_parcourus, l.conso_facturee, l.nb_prises, l.litres_declares,
        l.conso_declaree, l.conso_reference, l.ecart_reference_pct, l.ecart_declaree_pct, l.motif ?? '']));
  }
}
