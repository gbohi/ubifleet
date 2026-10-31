// UbiFleet — Relevés km › Utilisation du parc : km parcourus, jours
// d'utilisation, saisies manquantes, sauts de compteur suspects, révision.
import {
  ChangeDetectionStrategy, Component, ElementRef, OnDestroy, OnInit, computed, inject, signal, viewChild,
} from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AgenceApiService, VehiculeApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { Agence } from '../../../core/models';
import { InfoOngletComponent } from '../../../shared/info-onglet/info-onglet.component';
import {
  FiltresAnalyse, FiltresAnalyseComponent, exporterCsv,
} from '../../carburant/analyses/filtres-analyse.component';

@Component({
  selector: 'ubi-utilisation-parc',
  standalone: true,
  imports: [DecimalPipe, DatePipe, FiltresAnalyseComponent, InfoOngletComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['../../carburant/analyses/analyses.scss', './utilisation-parc.component.scss'],
  templateUrl: './utilisation-parc.component.html',
})
export class UtilisationParcComponent implements OnInit, OnDestroy {
  private api = inject(VehiculeApiService);
  private agenceApi = inject(AgenceApiService);
  private canvas = viewChild<ElementRef<HTMLCanvasElement>>('courbe');
  private graphe: any = null;

  agences = signal<Agence[]>([]);
  donnees = signal<any | null>(null);
  chargement = signal(false);
  erreur = signal('');
  vue = signal<'tous' | 'alertes' | 'inactifs'>('tous');
  detail = signal<any | null>(null);
  private filtres: FiltresAnalyse | null = null;
  private requete = 0;
  tri = signal<{ cle: string; asc: boolean }>({ cle: '', asc: false });

  lignes = computed(() => {
    const l = this.donnees()?.resultats ?? [];
    const v = this.vue();
    const filtrees = v === 'alertes' ? l.filter((x: any) => x.nb_sauts || x.sans_saisie_recente || (x.km_avant_revision ?? 1) <= 0)
      : v === 'inactifs' ? l.filter((x: any) => !x.km_parcourus) : l;
    const { cle, asc } = this.tri();
    if (!cle) return filtrees;
    const val = (x: any) => x[cle] ?? (asc ? Infinity : -Infinity);
    return [...filtrees].sort((a, b) => {
      const va = val(a), vb = val(b);
      const c = typeof va === 'string' ? va.localeCompare(vb) : va - vb;
      return asc ? c : -c;
    });
  });

  ngOnInit(): void {
    this.agenceApi.getAll().subscribe({
      next: (r: any) => this.agences.set(Array.isArray(r) ? r : (r?.results ?? [])), error: () => {},
    });
  }

  ngOnDestroy(): void { this.graphe?.destroy(); }

  charger(f: FiltresAnalyse): void {
    this.filtres = f;
    this.chargement.set(true);
    this.erreur.set('');
    const n = ++this.requete;   // seule la dernière demande s'affiche
    this.api.getUtilisationParc(f).subscribe({
      next: (r: any) => {
        if (n !== this.requete) return;
        this.donnees.set(r);
        this.chargement.set(false);
      },
      error: (err) => {
        if (n !== this.requete) return;
        this.erreur.set(messageErreurApi(err, 'Erreur lors du calcul.'));
        this.chargement.set(false);
      },
    });
  }

  trier(cle: string): void {
    const t = this.tri();
    this.tri.set({ cle, asc: t.cle === cle ? !t.asc : cle === 'immatriculation' });
  }

  revisionDepassee(l: any): boolean { return l.km_avant_revision !== null && l.km_avant_revision <= 0; }

  ouvrir(l: any): void {
    this.detail.set(l);
    if (!this.filtres) return;
    this.api.getCourbeCompteur({ vehicule: l.vehicule_id, date_debut: this.filtres.date_debut, date_fin: this.filtres.date_fin })
      .subscribe({ next: (r: any) => this.dessiner(r.points ?? [], l), error: () => {} });
  }

  fermer(): void { this.graphe?.destroy(); this.graphe = null; this.detail.set(null); }

  private dessiner(points: any[], l: any): void {
    import('chart.js/auto').then(({ default: Chart }) => setTimeout(() => {
      const el = this.canvas()?.nativeElement;
      if (!el) return;
      this.graphe?.destroy();
      const sauts = new Set((l.sauts ?? []).map((s: any) => s.au));
      this.graphe = new Chart(el, {
        type: 'line',
        data: {
          labels: points.map(p => new Date(p.quand).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })),
          datasets: [{
            label: 'Compteur (km)', data: points.map(p => p.km), borderColor: '#092440', backgroundColor: '#09244022',
            tension: .2, pointRadius: points.map(p => sauts.has(p.quand) ? 6 : 3),
            pointBackgroundColor: points.map(p => sauts.has(p.quand) ? '#ef4444' : p.source === 'relevé' ? '#3b82f6' : '#5bd988'),
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: {
            label: (c: any) => ` ${c.parsed.y.toLocaleString('fr-FR')} km — ${points[c.dataIndex].source}`
              + (sauts.has(points[c.dataIndex].quand) ? ' (saut suspect)' : '') } } },
          scales: { y: { ticks: { callback: (v: any) => Number(v).toLocaleString('fr-FR') } } },
        },
      } as any);
    }, 0));
  }

  exporter(): void {
    exporterCsv(`utilisation_parc_${this.filtres?.date_debut}_${this.filtres?.date_fin}.csv`,
      ['Véhicule', 'Marque', 'Modèle', 'Agence', 'Km début', 'Km fin', 'Km parcourus', "Jours d'utilisation",
       'Km par jour roulé', 'Saisies', 'Dernière saisie', 'Km dernière saisie', 'Jours sans saisie', 'Sauts suspects',
       'Km avant révision', 'Révision estimée le'],
      this.lignes().map((l: any) => [l.immatriculation, l.marque, l.modele, l.agence_nom, l.km_debut, l.km_fin,
        l.km_parcourus, l.jours_utilisation, l.km_par_jour_roule, l.nb_saisies, (l.derniere_saisie ?? '').slice(0, 10),
        l.derniere_saisie_km, l.jours_sans_saisie, l.nb_sauts, l.km_avant_revision, l.date_revision_estimee]));
  }
}
