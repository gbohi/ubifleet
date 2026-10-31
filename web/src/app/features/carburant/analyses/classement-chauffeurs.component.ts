// UbiFleet — Carburant › Chauffeurs : consommation de leurs prises (plein à
// plein) comparée à la référence des véhicules conduits.
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { CarburantApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { Agence } from '../../../core/models';
import { InfoOngletComponent } from '../../../shared/info-onglet/info-onglet.component';
import { FiltresAnalyse, FiltresAnalyseComponent, exporterCsv } from './filtres-analyse.component';

@Component({
  selector: 'ubi-classement-chauffeurs',
  standalone: true,
  imports: [DecimalPipe, FiltresAnalyseComponent, InfoOngletComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./analyses.scss'],
  template: `
    <ubi-info-onglet titre="Classement des chauffeurs" icone="fas fa-id-badge">
      Pour chaque chauffeur, la consommation des prises qu'il a faites (méthode plein à plein : litres ÷ km parcourus
      depuis la prise précédente du véhicule) est comparée à la consommation théorique de référence des véhicules
      qu'il a conduits, pondérée par les km. Un écart élevé et répété mérite un échange (conduite, charge,
      itinéraire) ; un écart sur un seul véhicule pointe plutôt le véhicule.
    </ubi-info-onglet>
    <ubi-filtres-analyse [agences]="agences()" [chargement]="chargement()" (appliquer)="charger($event)">
      <button class="btn btn-outline" [disabled]="!lignes().length" (click)="exporter()"><i class="fas fa-file-excel"></i> Exporter</button>
    </ubi-filtres-analyse>
    @if (erreur()) { <div class="an-notice"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }

    @if (lignes().length) {
      <div class="an-table-wrap">
        <table class="an-table">
          <thead><tr>
            <th class="num">#</th>
            <th class="triable" (click)="trier('chauffeur')">Chauffeur</th>
            <th class="num triable" (click)="trier('nb_prises')">Prises</th>
            <th class="num triable" (click)="trier('nb_vehicules')">Véhicules</th>
            <th class="num triable" (click)="trier('km_parcourus')">Km</th>
            <th class="num triable" (click)="trier('litres')">Litres</th>
            <th class="num triable" (click)="trier('montant')">Montant</th>
            <th class="num triable" (click)="trier('conso_moyenne')">Conso L/100</th>
            <th class="num">Référence</th>
            <th class="num triable" (click)="trier('ecart_pct')">Écart</th>
            <th class="num triable" (click)="trier('nb_anomalies')">Anomalies</th>
          </tr></thead>
          <tbody>
            @for (l of triees(); track l.chauffeur_id; let i = $index) {
              <tr>
                <td class="num muted">{{ i + 1 }}</td>
                <td class="fort" [class.muted]="!l.chauffeur_id">{{ l.chauffeur }}</td>
                <td class="num">{{ l.nb_prises }}</td>
                <td class="num">{{ l.nb_vehicules }}</td>
                <td class="num">{{ l.km_parcourus === null ? '—' : (l.km_parcourus | number:'1.0-0') }}</td>
                <td class="num">{{ l.litres | number:'1.0-2' }}</td>
                <td class="num">{{ l.montant | number:'1.0-0' }}</td>
                <td class="num fort">{{ l.conso_moyenne ?? '—' }}</td>
                <td class="num">{{ l.conso_reference ?? '—' }}</td>
                <td class="num" [class.ecart-pos]="(l.ecart_pct ?? 0) > 10" [class.ecart-neg]="(l.ecart_pct ?? 0) < -10">
                  {{ l.ecart_pct === null ? '—' : (l.ecart_pct > 0 ? '+' : '') + l.ecart_pct + ' %' }}</td>
                <td class="num" [class.ecart-pos]="l.nb_anomalies > 0">{{ l.nb_anomalies }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <p class="an-note">Référence : consommation théorique de référence des véhicules conduits (fiche véhicule), pondérée par les km.
        Les prises sans chauffeur sont regroupées en dernière ligne.</p>
    } @else if (!chargement()) {
      <div class="an-vide"><i class="fas fa-id-badge"></i> Aucune prise de carburant sur la période.</div>
    }
  `,
})
export class ClassementChauffeursComponent {
  agences = input<Agence[]>([]);
  private api = inject(CarburantApiService);

  lignes = signal<any[]>([]);
  chargement = signal(false);
  erreur = signal('');
  private filtres: FiltresAnalyse | null = null;
  private requete = 0;
  tri = signal<{ cle: string; asc: boolean }>({ cle: '', asc: false });

  triees = computed(() => {
    const { cle, asc } = this.tri();
    if (!cle) return this.lignes();
    const val = (l: any) => l[cle] ?? (asc ? Infinity : -Infinity);
    return [...this.lignes()].sort((a, b) => {
      const va = val(a), vb = val(b);
      const c = typeof va === 'string' ? va.localeCompare(vb) : va - vb;
      return asc ? c : -c;
    });
  });

  trier(cle: string): void {
    const t = this.tri();
    this.tri.set({ cle, asc: t.cle === cle ? !t.asc : cle === 'chauffeur' });
  }

  charger(f: FiltresAnalyse): void {
    this.filtres = f;
    this.chargement.set(true);
    this.erreur.set('');
    const n = ++this.requete;   // seule la dernière demande s'affiche
    this.api.getClassementChauffeurs(f).subscribe({
      next: (r: any) => { if (n !== this.requete) return; this.lignes.set(r.resultats ?? []); this.chargement.set(false); },
      error: (err) => {
        if (n !== this.requete) return;
        this.erreur.set(messageErreurApi(err, 'Erreur lors du calcul.'));
        this.chargement.set(false);
      },
    });
  }

  exporter(): void {
    exporterCsv(`classement_chauffeurs_${this.filtres?.date_debut}_${this.filtres?.date_fin}.csv`,
      ['Chauffeur', 'Prises', 'Véhicules', 'Km', 'Litres', 'Montant (FCFA)', 'Conso L/100', 'Référence', 'Écart %', 'Anomalies'],
      this.triees().map(l => [l.chauffeur, l.nb_prises, l.nb_vehicules, l.km_parcourus, l.litres, l.montant,
        l.conso_moyenne, l.conso_reference, l.ecart_pct, l.nb_anomalies]));
  }
}
