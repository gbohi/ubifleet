// UbiFleet — Dashboard Component (Angular 18 + NgRx Signals Store)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { BaseChartDirective } from 'ng2-charts';
import { ChartConfiguration, ChartData } from 'chart.js';

import { DashboardStore } from '../../store/dashboard/dashboard.store';
import { AlertesStore }   from '../../store/alertes/alertes.store';
import { AgenceApiService } from '../../core/services/api.service';
import { Agence } from '../../core/models';

@Component({
  selector: 'ubi-dashboard',
  standalone: true,
  imports: [
    RouterLink,
    DecimalPipe,
    BaseChartDirective,
  ],
  templateUrl: './dashboard.component.html',
  styleUrls:   ['./dashboard.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent implements OnInit {
  dashStore    = inject(DashboardStore);
  alertesStore = inject(AlertesStore);
  private agenceApi = inject(AgenceApiService);

  // Signal pour les agences (évite le problème d'itérabilité)
  agences = signal<Agence[]>([]);
  today   = new Date();

  moisList = [
    { val: 1,  label: 'Janvier'   },
    { val: 2,  label: 'Février'   },
    { val: 3,  label: 'Mars'      },
    { val: 4,  label: 'Avril'     },
    { val: 5,  label: 'Mai'       },
    { val: 6,  label: 'Juin'      },
    { val: 7,  label: 'Juillet'   },
    { val: 8,  label: 'Août'      },
    { val: 9,  label: 'Septembre' },
    { val: 10, label: 'Octobre'   },
    { val: 11, label: 'Novembre'  },
    { val: 12, label: 'Décembre'  },
  ];

  anneesDisponibles: number[] = [
    this.today.getFullYear(),
    this.today.getFullYear() - 1,
    this.today.getFullYear() - 2,
  ];

  // ── Chart: Évolution coûts (Line) ──
  get lineChartData(): ChartData<'line'> {
    const couts = this.dashStore.coutMensuelChart();
    // Données de démo si l'API n'est pas connectée
    const data = couts.length > 0 ? couts : this.demoLineData;
    return {
      labels: data.map((c: any) => {
        const m = this.moisList.find(x => x.val === (c.mois ?? c));
        return m ? m.label.substring(0, 3) : `M${c.mois}`;
      }),
      datasets: [{
        label: 'Coûts totaux (FCFA)',
        data: data.map((c: any) => c.total ?? c),
        borderColor: '#5bd988',
        backgroundColor: 'rgba(91,217,136,0.08)',
        pointBackgroundColor: '#5bd988',
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.4,
        fill: true,
      }]
    };
  }

  // Données de démo pour le graphique quand l'API est inaccessible
  private demoLineData = [
    { mois: 6,  total: 16800000 },
    { mois: 7,  total: 17200000 },
    { mois: 8,  total: 15900000 },
    { mois: 9,  total: 18100000 },
    { mois: 10, total: 17600000 },
    { mois: 11, total: 18800000 },
    { mois: 12, total: 19200000 },
    { mois: 1,  total: 17100000 },
    { mois: 2,  total: 16500000 },
    { mois: 3,  total: 18400000 },
    { mois: 4,  total: 17900000 },
    { mois: 5,  total: 18400000 },
  ];

  lineChartOptions: ChartConfiguration<'line'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#092440',
        titleColor: '#ffffff',
        bodyColor: 'rgba(255,255,255,0.7)',
        padding: 12,
        callbacks: {
          label: (ctx) =>
            ` ${new Intl.NumberFormat('fr-FR').format((ctx.parsed.y) ?? 0)} FCFA`
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { family: 'DM Sans', size: 11 }, color: '#94a3b8' }
      },
      y: {
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: {
          font: { family: 'DM Sans', size: 11 },
          color: '#94a3b8',
          callback: (v) => `${Number(v) / 1_000_000}M`
        }
      }
    }
  };

  // ── Chart: Répartition coûts (Doughnut) ──
  private categorieColors: Record<string, string> = {
    carburant:  '#5bd988',
    entretien:  '#092440',
    reparation: '#f59e0b',
    pneus:      '#8b5cf6',
    assurance:  '#ef4444',
    sinistre:   '#dc2626',
    controle:   '#0ea5e9',
    peage:      '#14b8a6',
    parking:    '#a855f7',
    divers:     '#3b82f6',
  };

  get doughnutChartData(): ChartData<'doughnut'> {
    const rep = this.dashStore.repartitionCouts();
    if (rep.length === 0) {
      return {
        labels: ['Aucune dépense enregistrée'],
        datasets: [{
          data: [1],
          backgroundColor: ['#e2e8f0'],
          borderWidth: 0,
        }]
      };
    }
    return {
      labels: rep.map(r => r.label),
      datasets: [{
        data: rep.map(r => r.montant),
        backgroundColor: rep.map(r => this.categorieColors[r.categorie] ?? '#94a3b8'),
        borderWidth: 0,
        hoverOffset: 6,
      }]
    };
  }

  doughnutChartOptions: ChartConfiguration<'doughnut'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          font: { family: 'DM Sans', size: 12 },
          boxWidth: 10,
          padding: 16,
          color: '#475569',
        }
      },
      tooltip: {
        backgroundColor: '#092440',
        titleColor: '#ffffff',
        bodyColor: 'rgba(255,255,255,0.7)',
        padding: 12,
        callbacks: {
          label: (ctx) => {
            const dataset = ctx.dataset.data as number[];
            const total = dataset.reduce((s, v) => s + v, 0);
            const pct = total > 0 ? Math.round((ctx.parsed / total) * 100) : 0;
            const montant = new Intl.NumberFormat('fr-FR').format(ctx.parsed);
            return ` ${ctx.label}: ${montant} FCFA (${pct}%)`;
          }
        }
      }
    }
  };

  // ── Chart: Top consommation (Bar horizontal) ──
  get barChartData(): ChartData<'bar'> {
    const top = this.dashStore.topConsommation().slice(0, 6);
    // Données de démo si vide
    const data = top.length > 0 ? top : this.demoBarData;
    return {
      labels: data.map((v: any) => v.vehicule__immatriculation ?? v.label),
      datasets: [{
        label: 'Litres',
        data: data.map((v: any) => v.litres ?? v.value),
        backgroundColor: '#5bd988',
        borderRadius: 6,
        borderSkipped: false,
      }]
    };
  }

  private demoBarData = [
    { label: 'CI-4521-AB', value: 340 },
    { label: 'CI-2234-BC', value: 298 },
    { label: 'CI-7890-AC', value: 245 },
    { label: 'CI-0087-ZZ', value: 210 },
    { label: 'CI-5566-GH', value: 189 },
    { label: 'CI-3345-DE', value: 178 },
  ];

  barChartOptions: ChartConfiguration<'bar'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#092440',
        titleColor: '#ffffff',
        bodyColor: 'rgba(255,255,255,0.7)',
        padding: 12,
        callbacks: {
          label: (ctx) => ` ${ctx.parsed.x ?? 0} L`
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { family: 'DM Sans', size: 11 }, color: '#94a3b8' }
      },
      y: {
        grid: { display: false },
        ticks: {
          font: { family: 'DM Sans', size: 12, weight: 600 },
          color: '#092440'
        }
      }
    }
  };

  ngOnInit(): void {
    // Charger les agences — protégé contre les erreurs API
    this.agenceApi.getAll().subscribe({
      next: (list) => {
        // Garantir que c'est toujours un tableau
        this.agences.set(Array.isArray(list) ? list : []);
      },
      error: () => this.agences.set([])
    });

    // Charger le dashboard — le store gère lui-même les états loading/error
    this.dashStore.loadDashboard();
    this.alertesStore.loadResume();
    this.alertesStore.loadAlertes();
  }

  onMoisChange(event: Event): void {
    const val = parseInt((event.target as HTMLSelectElement).value, 10);
    this.dashStore.setPeriode(val, this.dashStore.periode().annee);
    this.dashStore.loadDashboard();
  }

  onAnneeChange(event: Event): void {
    const val = parseInt((event.target as HTMLSelectElement).value, 10);
    this.dashStore.setPeriode(this.dashStore.periode().mois, val);
    this.dashStore.loadDashboard();
  }

  onAgenceChange(event: Event): void {
    const val = (event.target as HTMLSelectElement).value;
    this.dashStore.setAgenceFilter(val);
    this.dashStore.loadDashboard();
  }

  formatFCFA(value: number): string {
    if (!value || isNaN(value)) return '—';
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000)     return `${(value / 1_000).toFixed(0)} K`;
    return new Intl.NumberFormat('fr-FR').format(value);
  }

  alertePrioriteBadgeClass(priorite: string): string {
    const map: Record<string, string> = {
      critique: 'badge-danger',
      haute:    'badge-warning',
      normale:  'badge-info',
      basse:    'badge-gray',
    };
    return map[priorite] ?? 'badge-gray';
  }

  alerteDotClass(priorite: string): string {
    const map: Record<string, string> = {
      critique: 'red',
      haute:    'orange',
      normale:  'blue',
      basse:    'green',
    };
    return map[priorite] ?? 'blue';
  }
}
