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
    const data = this.dashStore.coutMensuelChart();
    return {
      // « Déc 25 », « Jan 26 » : les 12 mois se terminent au mois choisi
      labels: data.map((c: any) => {
        const m = this.moisList.find(x => x.val === c.mois);
        return `${m ? m.label.substring(0, 3) : 'M' + c.mois} ${String(c.annee).slice(-2)}`;
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
    const palette = ['#06b6d4', '#84cc16', '#f97316', '#ec4899', '#64748b'];   // catégories ajoutées dans les paramètres
    return {
      labels: rep.map(r => r.label),
      datasets: [{
        data: rep.map(r => r.montant),
        backgroundColor: rep.map((r, i) => this.categorieColors[r.categorie] ?? palette[i % palette.length]),
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

  // ── Chart : écart de consommation à la référence (barres horizontales, %) ──
  get barChartData(): ChartData<'bar'> {
    const top = this.dashStore.topEcartConso().slice(0, 6);
    return {
      labels: top.map((v: any) => v.vehicule__immatriculation),
      datasets: [{
        label: 'Écart à la référence (%)',
        data: top.map((v: any) => v.ecart_pct),
        backgroundColor: top.map((v: any) => v.ecart_pct > 10 ? '#ef4444' : v.ecart_pct > 0 ? '#f59e0b' : '#5bd988'),
        borderRadius: 6,
        borderSkipped: false,
      }]
    };
  }

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
          label: (ctx) => {
            const v: any = this.dashStore.topEcartConso()[ctx.dataIndex];
            return v ? ` ${v.ecart_pct > 0 ? '+' : ''}${v.ecart_pct} % — ${v.conso} L/100 (réf. ${v.reference})` : '';
          }
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

  /** Couleur d'un statut véhicule (Paramètres › Statuts véhicule) → classe de la barre. */
  classeStatut(couleur: string): string {
    return ({ green: 'green', orange: 'warning', red: 'danger', blue: 'blue', gray: 'gray' } as Record<string, string>)[couleur] ?? 'gray';
  }

  /** Export Excel (CSV) de la page : indicateurs, parc, coûts, alertes prioritaires. */
  exporter(): void {
    const d: any = this.dashStore.data();
    if (!d) return;
    const cell = (v: any) => `"${String(typeof v === 'number' && !Number.isInteger(v) ? v.toFixed(2).replace('.', ',') : v ?? '').replace(/"/g, '""')}"`;
    const l = (...c: any[]) => c.map(cell).join(';');
    const agence = this.agences().find(a => a.id === this.dashStore.agenceFilter())?.nom ?? 'Toutes les agences';
    const n = (v: any) => Number(v) || 0;
    const lignes = [
      l(`Tableau de bord UbiFleet — ${this.dashStore.periodLabel()} — ${agence}`), '',
      l('Indicateur', 'Valeur'),
      l('Véhicules actifs', d.parc.total), ...d.parc.par_statut.map((s: any) => l(`  ${s.libelle}`, s.nb)),
      l('Carburant — montant (FCFA)', n(d.carburant.montant)), l('Carburant — volume (L)', n(d.carburant.volume)),
      l('Consommation moyenne (L/100 km)', n(d.carburant.conso_moy)), l('Anomalies de consommation', d.carburant.anomalies),
      l('Entretiens planifiés', d.entretien.planifiees), l('Entretiens terminés', d.entretien.terminees),
      l('Coût des entretiens terminés (FCFA)', n(d.entretien.cout)),
      l('Alertes à traiter', d.alertes.total), l('dont critiques', d.alertes.critiques),
      l('Sinistres en cours', d.sinistres.en_cours),
      l('Assurances expirant dans 30 jours', d.assurances_critiques), l('Véhicules avec assurance expirée', d.assurances_expirees ?? 0),
      ...(d.chauffeurs ? [l('Chauffeurs en poste', d.chauffeurs.total), l('Permis expirés', d.chauffeurs.permis_expires),
        l('Permis à renouveler (60 j)', d.chauffeurs.permis_a_renouveler), l('Documents chauffeur expirés', d.chauffeurs.documents_expires)] : []),
      '', l('Mois', 'Coûts (FCFA)'), ...d.cout_mensuel.map((m: any) => l(`${this.moisList[m.mois - 1].label} ${m.annee}`, n(m.total))),
      '', l('Catégorie', 'Montant du mois (FCFA)'), ...d.repartition_couts.map((r: any) => l(r.label, n(r.montant))),
      '', l('Véhicule', 'Conso (L/100 km)', 'Référence', 'Écart (%)'),
      ...d.top_ecart_conso.map((v: any) => l(v.vehicule__immatriculation, n(v.conso), n(v.reference), n(v.ecart_pct))),
      '', l('Alerte prioritaire', 'Priorité', 'Véhicule', 'Chauffeur'),
      ...d.alertes.prioritaires.map((a: any) => l(a.titre, a.priorite_display, a.vehicule_immat ?? '', a.chauffeur_nom ?? '')),
    ];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + lignes.join('\r\n')], { type: 'text/csv;charset=utf-8;' }));
    a.download = `tableau_de_bord_${this.dashStore.periode().annee}_${String(this.dashStore.periode().mois).padStart(2, '0')}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  formatFCFA(value: number): string {
    value = Number(value);
    if (isNaN(value)) return '—';
    if (!value) return '0';
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
