// UbiFleet — Carburant › Suivi tournées
//
// Une ligne par tournée effectuée (somme de ses prises, réel vs théorique figé
// à l'ouverture) et une ligne par prise hors tournée (litres estimés d'après
// la consommation théorique de référence du véhicule). Synthèse : part du
// carburant consommé hors tournée. Clôture / réouverture / annulation selon
// les droits du rôle (Administration › Permissions).
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { CarburantApiService } from '../../../core/services/api.service';
import { FenetreSaisieService, heureLocale, messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { OptionTournee, OptionsSaisieService } from '../../../core/services/options-saisie.service';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { Agence } from '../../../core/models';

type Vue = 'tournees' | 'hors';
interface Droits { cloturer: boolean; rouvrir: boolean; annuler: boolean; }

const aujourdhui = () => new Date().toISOString().split('T')[0];
const debutDuMois = () => aujourdhui().substring(0, 8) + '01';

@Component({
  selector: 'ubi-suivi-tournees',
  standalone: true,
  imports: [DatePipe, DecimalPipe, RouterLink],
  templateUrl: './suivi-tournees.component.html',
  styleUrls: ['./suivi-tournees.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SuiviTourneesComponent implements OnInit {
  agences = input<Agence[]>([]);

  private api = inject(CarburantApiService);
  private options = inject(OptionsSaisieService);
  private fenetres = inject(FenetreSaisieService);
  readonly typesMvt = inject(TypesMouvementService);

  vue = signal<Vue>('tournees');
  // Filtres
  dateDebut = signal(debutDuMois());
  dateFin   = signal(aujourdhui());
  agence    = signal('');
  immat     = signal('');
  tournee   = signal('');
  statut    = signal('');
  typeMvt   = signal('');
  tournees  = signal<OptionTournee[]>([]);

  chargement = signal(false);
  erreur     = signal('');
  notice     = signal('');
  synthese   = signal<any | null>(null);
  lignes     = signal<any[]>([]);
  horsLignes = signal<any[]>([]);
  droits     = signal<Droits>({ cloturer: false, rouvrir: false, annuler: false });
  ouvertes   = signal<Set<string>>(new Set());

  /** Types hors tournée proposés au filtre et à l'annulation. */
  typesHors = computed(() => this.typesMvt.tous().filter(t => t.pour_prises && t.code !== 'tournee'));

  totaux = computed(() => {
    const l = this.lignes();
    const s = (k: string) => l.reduce((a, x) => a + (x[k] ?? 0), 0);
    return { vol_reel: s('vol_reel'), montant_reel: s('montant_reel'), km_parcouru: s('km_parcouru'),
             vol_theorique: s('vol_theorique'), montant_theorique: s('montant_theorique'),
             ecart_dotation: s('ecart_dotation'), nb_prises: s('nb_prises') };
  });
  totauxHors = computed(() => {
    const l = this.horsLignes();
    const s = (k: string) => l.reduce((a, x) => a + (x[k] ?? 0), 0);
    return { vol_reel: s('vol_reel'), montant_reel: s('montant_reel'), km_parcouru: s('km_parcouru'),
             vol_estime: s('vol_estime'), ecart: s('ecart') };
  });

  // Clôture
  aCloturer   = signal<any | null>(null);
  kmRetour    = signal<number | null>(null);
  dateFinClo  = signal('');
  heureFinClo = signal('');
  commentaire = signal('');
  // Annulation
  aAnnuler    = signal<any | null>(null);
  typeAnnul   = signal('');
  motifAnnul  = signal('');
  actionEnCours = signal(false);
  actionErreur  = signal('');

  ngOnInit(): void {
    this.typesMvt.charger();
    this.fenetres.charger();
    this.options.tournees().subscribe({ next: l => this.tournees.set(l), error: () => {} });
    this.charger();
  }

  private filtres(): Record<string, string> {
    const f: Record<string, string> = {};
    if (this.dateDebut()) f['date_debut'] = this.dateDebut();
    if (this.dateFin())   f['date_fin'] = this.dateFin();
    if (this.agence())    f['agence'] = this.agence();
    if (this.immat())     f['immatriculation'] = this.immat();
    return f;
  }

  charger(): void {
    this.chargement.set(true);
    this.erreur.set('');
    const base = this.filtres();
    const ft = { ...base, ...(this.tournee() ? { tournee: this.tournee() } : {}), ...(this.statut() ? { statut: this.statut() } : {}) };
    const fh = { ...base, ...(this.typeMvt() ? { type_mouvement: this.typeMvt() } : {}) };
    forkJoin({
      syn: this.api.getSyntheseTournees(base),
      t: this.api.getSuiviTournees(ft),
      h: this.api.getSuiviHorsTournee(fh),
    }).subscribe({
      next: ({ syn, t, h }) => {
        this.synthese.set(syn);
        this.lignes.set(t.resultats ?? []);
        this.droits.set(t.droits ?? this.droits());
        this.horsLignes.set(h.resultats ?? []);
        this.chargement.set(false);
      },
      error: (err) => { this.erreur.set(messageErreurApi(err, 'Erreur lors du chargement.')); this.chargement.set(false); },
    });
  }

  reinitialiser(): void {
    this.dateDebut.set(debutDuMois()); this.dateFin.set(aujourdhui());
    this.agence.set(''); this.immat.set(''); this.tournee.set(''); this.statut.set(''); this.typeMvt.set('');
    this.charger();
  }

  basculer(id: string): void {
    const s = new Set(this.ouvertes());
    s.has(id) ? s.delete(id) : s.add(id);
    this.ouvertes.set(s);
  }

  classeEcart(v: number | null | undefined): string {
    if (v === null || v === undefined) return '';
    return v > 0 ? 'ecart-pos' : v < 0 ? 'ecart-neg' : '';
  }

  classeType(couleur: string): string {
    return ({ green: 'badge-green', orange: 'badge-warning', blue: 'badge-info', red: 'badge-danger' } as any)[couleur] ?? 'badge-gray';
  }

  // ── Clôture ──
  ouvrirCloture(l: any): void {
    this.actionErreur.set('');
    this.aCloturer.set(l);
    this.kmRetour.set(l.km_retour);
    this.dateFinClo.set(this.fenetres.max('releves') ?? aujourdhui());
    this.heureFinClo.set(this.fenetres.heureServeur() ?? heureLocale());
    this.commentaire.set(l.commentaire ?? '');
  }

  confirmerCloture(): void {
    const l = this.aCloturer();
    if (!l || this.actionEnCours()) return;
    this.actionEnCours.set(true);
    this.api.cloturerTournee(l.id, {
      km_retour: this.kmRetour(), date_fin: this.dateFinClo() || null, heure_fin: this.heureFinClo() || null,
      commentaire: this.commentaire(),
    }).subscribe({
      next: () => { this.terminerAction(`Tournée n° ${l.numero} clôturée.`); this.aCloturer.set(null); },
      error: (err) => { this.actionEnCours.set(false); this.actionErreur.set(messageErreurApi(err, 'Clôture impossible.')); },
    });
  }

  rouvrir(l: any): void {
    if (!confirm(`Rouvrir la tournée n° ${l.numero} ? Son KM retour et son relevé de retour seront supprimés.`)) return;
    this.api.rouvrirTournee(l.id).subscribe({
      next: () => this.terminerAction(`Tournée n° ${l.numero} rouverte.`),
      error: (err) => this.erreur.set(messageErreurApi(err, 'Réouverture impossible.')),
    });
  }

  // ── Annulation ──
  ouvrirAnnulation(l: any): void {
    this.actionErreur.set('');
    this.aAnnuler.set(l);
    this.typeAnnul.set(this.typesHors().find(t => t.actif)?.code ?? '');
    this.motifAnnul.set('');
  }

  confirmerAnnulation(): void {
    const l = this.aAnnuler();
    if (!l || this.actionEnCours()) return;
    this.actionEnCours.set(true);
    this.api.annulerTournee(l.id, { type_mouvement: this.typeAnnul(), motif: this.motifAnnul() }).subscribe({
      next: () => { this.terminerAction(`Tournée n° ${l.numero} annulée.`); this.aAnnuler.set(null); },
      error: (err) => { this.actionEnCours.set(false); this.actionErreur.set(messageErreurApi(err, 'Annulation impossible.')); },
    });
  }

  private terminerAction(message: string): void {
    this.actionEnCours.set(false);
    this.notice.set(message);
    setTimeout(() => this.notice.set(''), 4000);
    this.charger();
  }

  // ── Export (CSV lisible par Excel, colonnes dans l'ordre du fichier de suivi) ──
  exporter(): void {
    const n = (v: any) => v === null || v === undefined ? '' : String(v).replace('.', ',');
    const d = (v: string | null) => v ? v.split('-').reverse().join('/') : '';
    let entetes: string[], lignes: string[][], nom: string;
    if (this.vue() === 'tournees') {
      entetes = ['Date', 'Date fin', 'N° tournée', 'Statut', 'Véhicule', 'Libelle tournée', 'Dotation réelle (L)',
        'Montant réel (FCFA)', 'Type véhicule', 'KM depart', 'KM de retour', 'KM Parcouru', 'Km théorique',
        'Dotation théorique (L)', 'Montant théorique (FCFA)', 'Conso au 100 réelle', 'Conso au 100 Theo',
        'Ecart dotation (L)', 'Ecart conso 100', 'Nb prises', 'Chauffeur', 'Commentaire'];
      lignes = this.lignes().map(l => [d(l.date_debut), d(l.date_fin), l.numero, l.statut_display, l.immatriculation,
        `${l.tournee_code} — ${l.tournee_libelle}`, n(l.vol_reel), n(l.montant_reel), l.type_vehicule, n(l.km_depart),
        n(l.km_retour), n(l.km_parcouru), n(l.km_theorique), n(l.vol_theorique), n(l.montant_theorique), n(l.conso_reel),
        n(l.conso_theorique), n(l.ecart_dotation), n(l.ecart_conso), n(l.nb_prises), l.chauffeur_nom ?? '',
        (l.commentaire ?? '').replace(/\s+/g, ' ')]);
      nom = 'suivi_tournees';
    } else {
      entetes = ['Date', 'Heure', 'Véhicule', 'Type de mouvement', 'Type véhicule', 'Chauffeur', 'KM depart',
        'KM de retour', 'KM Parcouru', 'Litres réels', 'Montant réel (FCFA)', 'Conso au 100 réelle',
        'Conso de référence', 'Litres estimés', 'Ecart (L)', 'Notes'];
      lignes = this.horsLignes().map(l => [d(l.date), (l.heure ?? '').substring(0, 5), l.immatriculation, l.type_display,
        l.type_vehicule, l.chauffeur_nom ?? '', n(l.km_depart), n(l.km_retour), n(l.km_parcouru), n(l.vol_reel),
        n(l.montant_reel), n(l.conso_reel), n(l.conso_reference), n(l.vol_estime), n(l.ecart),
        (l.notes ?? '').replace(/\s+/g, ' ')]);
      nom = 'suivi_hors_tournee';
    }
    const csv = '﻿' + [entetes, ...lignes].map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(';')).join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    a.download = `${nom}_${this.dateDebut() || 'debut'}_${this.dateFin() || 'fin'}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
}
