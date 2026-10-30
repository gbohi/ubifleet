// UbiFleet — Carburant › Évolution par agence (mensuelle)
import {
  ChangeDetectionStrategy, Component, ElementRef, OnDestroy, computed, inject, input, signal, viewChild,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { CarburantApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { Agence } from '../../../core/models';
import { FiltresAnalyse, FiltresAnalyseComponent, exporterCsv } from './filtres-analyse.component';

type Mesure = 'volume' | 'montant' | 'nb' | 'km' | 'conso';
type Vue = 'agences' | 'decoupage';

const COULEURS = ['#092440', '#5bd988', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316', '#ec4899'];
const MESURES: { code: Mesure; libelle: string; unite: string }[] = [
  { code: 'volume', libelle: 'Litres', unite: 'L' }, { code: 'montant', libelle: 'Montant', unite: 'FCFA' },
  { code: 'nb', libelle: 'Prises', unite: 'prise(s)' }, { code: 'km', libelle: 'Km', unite: 'km' },
  { code: 'conso', libelle: 'Conso L/100', unite: 'L/100 km' },
];
const MOIS_FR = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const libelleMois = (m: string) => `${MOIS_FR[Number(m.slice(5, 7)) - 1]} ${m.slice(0, 4)}`;

@Component({
  selector: 'ubi-evolution-agences',
  standalone: true,
  imports: [DecimalPipe, FiltresAnalyseComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./analyses.scss'],
  styles: [`
    .ev-barre { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 10px; }
    .ev-graphe { position: relative; height: 340px; padding: 14px; background: white; margin-bottom: 14px;
                 border: 1px solid var(--gray-200); border-radius: var(--radius-lg); }
  `],
  template: `
    <div class="an-entete">
      <h2><i class="fas fa-chart-line"></i> Évolution par agence</h2>
      <p>Mois par mois (un mois sans prise vaut 0) : litres, montant, nombre de prises, km parcourus et consommation.
        La vue « Tournées / hors tournée » découpe chaque mois et ajoute la dotation théorique des tournées commencées dans le mois.</p>
    </div>
    <ubi-filtres-analyse [agences]="agences()" [chargement]="chargement()" (appliquer)="charger($event)">
      <button class="btn btn-outline" [disabled]="!donnees()" (click)="exporter()"><i class="fas fa-file-excel"></i> Exporter</button>
    </ubi-filtres-analyse>
    @if (erreur()) { <div class="an-notice"><i class="fas fa-exclamation-triangle"></i> {{ erreur() }}</div> }

    @if (donnees(); as d) {
      @if (d.agences.length) {
        <div class="ev-barre">
          <div class="an-choix">
            @for (m of mesures; track m.code) {
              <button [class.active]="mesure() === m.code" (click)="choisirMesure(m.code)">{{ m.libelle }}</button>
            }
          </div>
          <div class="an-choix">
            <button [class.active]="vue() === 'agences'" (click)="choisirVue('agences')">Par agence</button>
            <button [class.active]="vue() === 'decoupage'" [disabled]="mesure() === 'km' || mesure() === 'conso'"
                    (click)="choisirVue('decoupage')">Tournées / hors tournée</button>
          </div>
        </div>
        <div class="ev-graphe"><canvas #canvas></canvas></div>

        <div class="an-table-wrap">
          <table class="an-table">
            <thead><tr>
              <th>Mois</th>
              @for (a of d.agences; track a.nom) { <th class="num">{{ a.nom }}</th> }
              @if (d.agences.length > 1) { <th class="num">Total</th> }
              @if (mesure() === 'volume') { <th class="num">dont tournées</th><th class="num">dont hors tournée</th><th class="num">Dotation théorique</th> }
            </tr></thead>
            <tbody>
              @for (m of d.mois; track m; let i = $index) {
                <tr>
                  <td class="nowrap">{{ libelleMois(m) }}</td>
                  @for (a of d.agences; track a.nom) { <td class="num">{{ valeur(a.points[i]) }}</td> }
                  @if (d.agences.length > 1) { <td class="num fort">{{ totalMois(i) }}</td> }
                  @if (mesure() === 'volume') {
                    <td class="num">{{ somme(i, 'volume_tournee') | number:'1.0-0' }}</td>
                    <td class="num">{{ somme(i, 'volume_hors') | number:'1.0-0' }}</td>
                    <td class="num">{{ somme(i, 'dotation_theorique') | number:'1.0-0' }}</td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </div>
        <p class="an-note">Conso = litres des prises ayant un km parcouru ÷ km × 100 (méthode plein à plein).</p>
      } @else {
        <div class="an-vide"><i class="fas fa-chart-line"></i> Aucune prise de carburant sur la période.</div>
      }
    }
  `,
})
export class EvolutionAgencesComponent implements OnDestroy {
  agences = input<Agence[]>([]);
  private api = inject(CarburantApiService);
  private canvas = viewChild<ElementRef<HTMLCanvasElement>>('canvas');
  private graphe: any = null;

  readonly mesures = MESURES;
  readonly libelleMois = libelleMois;
  donnees = signal<{ mois: string[]; agences: { nom: string; points: any[] }[] } | null>(null);
  mesure = signal<Mesure>('volume');
  vue = signal<Vue>('agences');
  chargement = signal(false);
  erreur = signal('');
  private filtres: FiltresAnalyse | null = null;

  private unite = computed(() => MESURES.find(m => m.code === this.mesure())!.unite);

  ngOnDestroy(): void { this.graphe?.destroy(); }

  charger(f: FiltresAnalyse): void {
    this.filtres = f;
    this.chargement.set(true);
    this.erreur.set('');
    this.api.getEvolutionAgences(f).subscribe({
      next: (r: any) => { this.donnees.set({ mois: r.mois ?? [], agences: r.agences ?? [] }); this.chargement.set(false); this.dessiner(); },
      error: (err) => { this.erreur.set(messageErreurApi(err, 'Erreur lors du chargement.')); this.chargement.set(false); },
    });
  }

  choisirMesure(m: Mesure): void {
    this.mesure.set(m);
    if ((m === 'km' || m === 'conso') && this.vue() === 'decoupage') this.vue.set('agences');
    this.dessiner();
  }
  choisirVue(v: Vue): void { this.vue.set(v); this.dessiner(); }

  /** Valeur d'un mois (conso : recalculée à partir des litres et km pour les totaux). */
  valeur(p: any): string {
    const v = p[this.mesure()];
    if (v === null || v === undefined) return '—';
    return this.mesure() === 'conso' ? String(v) : Math.round(v).toLocaleString('fr-FR');
  }
  somme(i: number, cle: string): number {
    return (this.donnees()?.agences ?? []).reduce((a, ag) => a + (ag.points[i][cle] ?? 0), 0);
  }
  totalMois(i: number): string {
    if (this.mesure() !== 'conso') return Math.round(this.somme(i, this.mesure())).toLocaleString('fr-FR');
    const km = this.somme(i, 'km');
    const litres = (this.donnees()?.agences ?? []).reduce((a, ag) => a + (ag.points[i].conso ?? 0) * ag.points[i].km / 100, 0);
    return km ? (litres / km * 100).toFixed(2) : '—';
  }

  private dessiner(): void {
    // Chart.js est une dépendance de l'application : chargé à la demande, sans CDN
    import('chart.js/auto').then(({ default: Chart }) => setTimeout(() => {
      const el = this.canvas()?.nativeElement, d = this.donnees();
      if (!el || !d) return;
      this.graphe?.destroy();
      const labels = d.mois.map(libelleMois), m = this.mesure();
      let datasets: any[], type: any = 'line', empile = false;
      if (this.vue() === 'decoupage') {
        type = 'bar'; empile = true;
        const s = (cle: string) => d.mois.map((_, i) => this.somme(i, cle));
        datasets = [
          { label: 'Tournées', data: s(`${m}_tournee`), backgroundColor: COULEURS[0], stack: 'r' },
          { label: 'Hors tournée', data: s(`${m}_hors`), backgroundColor: COULEURS[3], stack: 'r' },
        ];
        if (m === 'volume') datasets.push({ type: 'line', label: 'Dotation théorique (tournées)', data: s('dotation_theorique'),
          borderColor: COULEURS[1], backgroundColor: COULEURS[1], borderDash: [6, 4], borderWidth: 2, pointRadius: 3, tension: .3 });
      } else {
        datasets = d.agences.map((a, i) => ({
          label: a.nom, data: a.points.map(p => p[m]), borderColor: COULEURS[i % COULEURS.length],
          backgroundColor: COULEURS[i % COULEURS.length] + '22', borderWidth: 2.5, pointRadius: 4, tension: .35, spanGaps: true,
        }));
      }
      const unite = this.unite();
      this.graphe = new Chart(el, {
        type, data: { labels, datasets },
        options: {
          responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
          plugins: { legend: { position: 'bottom' },
            tooltip: { callbacks: { label: (c: any) => `${c.dataset.label} : ${(c.parsed.y ?? 0).toLocaleString('fr-FR')} ${unite}` } } },
          scales: { x: { stacked: empile, grid: { color: '#f0f0f0' } },
                    y: { stacked: empile, beginAtZero: true, grid: { color: '#f0f0f0' }, title: { display: true, text: unite } } },
        },
      } as any);
    }, 0));
  }

  exporter(): void {
    const d = this.donnees();
    if (!d) return;
    const entetes = ['Agence', 'Mois', 'Litres', 'Litres tournées', 'Litres hors tournée', 'Montant (FCFA)', 'Prises',
      'Km', 'Conso L/100', 'Dotation théorique (L)'];
    const lignes = d.agences.flatMap(a => a.points.map(p => [a.nom, p.mois, p.volume, p.volume_tournee, p.volume_hors,
      p.montant, p.nb, p.km, p.conso, p.dotation_theorique]));
    exporterCsv(`evolution_agences_${this.filtres?.date_debut}_${this.filtres?.date_fin}.csv`, entetes, lignes);
  }
}
