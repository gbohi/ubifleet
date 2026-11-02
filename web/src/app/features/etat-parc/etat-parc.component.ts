// UbiFleet — État du Parc (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { DatePipe, DecimalPipe } from '@angular/common';
import { VehiculeApiService } from '../../core/services/api.service';

interface VehiculeEtat {
  id: string;
  immatriculation: string;
  marque: string; modele: string; annee: number;
  type_vehicule: string;
  statut: string; statut_display: string; statut_couleur: string; disponible: boolean;
  agence_nom: string | null;
  chauffeur_nom: string | null;
  kilometrage_actuel: number;
  km_prevu_revision: number | null;
  km_restant_revision: number | null;
  statut_revision: string;
  km_prevu_pneus: number | null;
  km_restant_pneus: number | null;
  statut_pneus: string;
  jr_assurance: number | null;     statut_assurance: string;
  jr_ct: number | null;            statut_ct: string;
  jr_carte_transport: number | null; statut_carte_transport: string;
  jr_vignette: number | null;      statut_vignette: string;
  age_mois: number | null;
  chauffeur_id: string | null;
  notes: string;
}

interface Kpis {
  total: number; disponibles: number; indisponibles: number;
  revision_urgente: number; revision_attention: number;
  docs_expires: number; docs_urgents: number; pneus_urgents: number;
}

@Component({
  selector: 'ubi-etat-parc',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './etat-parc.component.html',
  styleUrls: ['./etat-parc.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EtatParcComponent implements OnInit {
  private api = inject(VehiculeApiService);
  private auth = inject(AuthService);
  peutReglerSeuils = computed(() => this.auth.peutAcceder('parametres'));

  loading   = signal(false);
  // Seuils par échéance (Paramètres › Échéances), ex. seuils()?.['ct'].urgent
  seuils    = signal<Record<string, { attention: number; urgent: number }> | null>(null);
  kpis      = signal<Kpis | null>(null);
  vehicules = signal<VehiculeEtat[]>([]);
  error     = signal('');

  // Filtres
  filterAgence  = signal('');
  filterType    = signal('');
  filterStatut  = signal('');
  filterTexte   = signal('');
  filterAlerte  = signal('');   // 'revision' | 'pneus' | 'docs' | ''


  statuts = signal<{ code: string; libelle: string }[]>([]);

  // Agences et types pour les sélecteurs
  agences = computed(() => {
    const set = new Set(this.vehicules().map(v => v.agence_nom).filter(Boolean));
    return Array.from(set).sort() as string[];
  });
  types = computed(() => {
    const set = new Set(this.vehicules().map(v => v.type_vehicule).filter(Boolean));
    return Array.from(set).sort() as string[];
  });
  nbFiltresActifs = computed(() =>
    [this.filterTexte(), this.filterAgence(), this.filterType(), this.filterStatut(), this.filterAlerte()]
      .filter(v => !!v).length);

  private static readonly DOCS = ['assurance', 'ct', 'carte_transport', 'vignette'] as const;

  vehiculesFiltres = computed(() => {
    let list = this.vehicules();
    const txt    = this.filterTexte().trim().toLowerCase();
    const agence = this.filterAgence();
    const type   = this.filterType();
    const statut = this.filterStatut();
    const alerte = this.filterAlerte();
    const st = (v: VehiculeEtat, k: string) => (v as any)[`statut_${k}`] as string;

    if (txt)    list = list.filter(v =>
      v.immatriculation.toLowerCase().includes(txt) ||
      (v.marque || '').toLowerCase().includes(txt) ||
      (v.modele || '').toLowerCase().includes(txt) ||
      (v.chauffeur_nom || '').toLowerCase().includes(txt)
    );
    if (agence) list = list.filter(v => v.agence_nom === agence);
    if (type)   list = list.filter(v => v.type_vehicule === type);
    if (statut === '__dispo')   list = list.filter(v => v.disponible);
    else if (statut === '__indispo') list = list.filter(v => !v.disponible);
    else if (statut === '__sans') list = list.filter(v => !v.statut);
    else if (statut) list = list.filter(v => v.statut === statut);
    // Mêmes règles que les indicateurs du haut
    if (alerte === 'revision') list = list.filter(v => ['urgent', 'depasse'].includes(v.statut_revision));
    if (alerte === 'revision_attention') list = list.filter(v => v.statut_revision === 'attention');
    if (alerte === 'pneus') list = list.filter(v => ['urgent', 'depasse'].includes(v.statut_pneus));
    if (alerte === 'docs_expires') list = list.filter(v => EtatParcComponent.DOCS.some(k => st(v, k) === 'depasse'));
    if (alerte === 'docs') list = list.filter(v => EtatParcComponent.DOCS.some(k => ['urgent', 'depasse'].includes(st(v, k))));
    if (alerte === 'nc') list = list.filter(v =>
      [...EtatParcComponent.DOCS, 'revision'].some(k => st(v, k) === 'nc'));
    return list;
  });

  /** Légende : seuils réels (Paramètres › Échéances). */
  legende = computed(() => {
    const s = this.seuils();
    if (!s) return null;
    const km = s['revision'], j = s['assurance'];
    return {
      attention: `révision ≤ ${new Intl.NumberFormat('fr-FR').format(km?.attention ?? 0)} km, documents ≤ ${j?.attention ?? 0} j`,
      urgent: `révision ≤ ${new Intl.NumberFormat('fr-FR').format(km?.urgent ?? 0)} km, documents ≤ ${j?.urgent ?? 0} j`,
    };
  });

  ngOnInit(): void { this.loadEtatParc(); }

  loadEtatParc(): void {
    this.loading.set(true); this.error.set('');
    this.api.getEtatParc().subscribe({
      next: (res) => {
        this.kpis.set(res.kpis);
        this.seuils.set(res.seuils ?? null);
        this.vehicules.set(res.vehicules ?? []);
        // Véhicules sans statut : code vide, distingué de « Tous »
        this.statuts.set((res.statuts ?? []).map((st: any) => ({ ...st, code: st.code || '__sans' })));
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Erreur de chargement.');
        this.loading.set(false);
      },
    });
  }

  onFilter(field: string, e: Event): void {
    const val = (e.target as HTMLInputElement | HTMLSelectElement).value;
    if (field === 'texte')  this.filterTexte.set(val);
    if (field === 'agence') this.filterAgence.set(val);
    if (field === 'type')   this.filterType.set(val);
    if (field === 'statut') this.filterStatut.set(val);
    if (field === 'alerte') this.filterAlerte.set(val);
  }

  /** Clic sur un indicateur : filtre le tableau (un second clic l'enlève). */
  filtrerKpi(statut: string, alerte: string): void {
    const actif = this.filterStatut() === statut && this.filterAlerte() === alerte;
    this.filterStatut.set(actif ? '' : statut);
    this.filterAlerte.set(actif ? '' : alerte);
  }
  kpiActif(statut: string, alerte: string): boolean {
    return (statut || alerte) !== '' && this.filterStatut() === statut && this.filterAlerte() === alerte;
  }

  resetFiltres(): void {
    this.filterTexte.set(''); this.filterAgence.set('');
    this.filterType.set(''); this.filterStatut.set('');
    this.filterAlerte.set('');
  }

  formatAge(mois: number | null): string {
    if (mois === null || mois === undefined) return '—';
    const m = Math.round(mois);
    const a = Math.floor(m / 12), r = m % 12;
    if (!a) return `${r} mois`;
    return r ? `${a} an${a > 1 ? 's' : ''} ${r} m` : `${a} an${a > 1 ? 's' : ''}`;
  }

  // ── Helpers indicateurs ──────────────────────────────────────
  badgeStatut(statut: string): string {
    const map: Record<string,string> = {
      ok:        'ind-ok',
      attention: 'ind-attention',
      urgent:    'ind-urgent',
      depasse:   'ind-depasse',
      nc:        'ind-nc',
    };
    return map[statut] ?? 'ind-nc';
  }

  badgeStatutVehicule(couleur: string): string {
    const map: Record<string,string> = {
      green: 'badge-green', orange: 'badge-warning',
      red: 'badge-danger', blue: 'badge-blue', gray: 'badge-gray',
    };
    return map[couleur] ?? 'badge-gray';
  }

  formatKm(val: number | null): string {
    if (val === null || val === undefined) return 'N/C';
    if (val <= 0) return `Dépassé (${new Intl.NumberFormat('fr-FR').format(Math.abs(val))} km)`;
    return new Intl.NumberFormat('fr-FR').format(val) + ' km';
  }

  formatJours(val: number | null): string {
    if (val === null || val === undefined) return 'N/C';
    if (val < 0) return `Expiré (${Math.abs(val)} j)`;
    if (val === 0) return 'Aujourd\'hui';
    return `${val} jour${val > 1 ? 's' : ''}`;
  }

  // ── Export CSV ────────────────────────────────────────────────
  exportCsv(): void {
    const libelles: Record<string, string> = { ok: 'OK', attention: 'Attention', urgent: 'Urgent', depasse: 'Dépassé', nc: 'Non renseigné' };
    const lib = (st: string) => libelles[st] ?? st;
    const hdrs = [
      'Immatriculation','Type','Marque','Modèle','Année','Agence','Chauffeur',
      'Km actuel','Disponible','Statut',
      'Km prévu révision','Km restant révision','Révision',
      'Km prévu pneus','Km restant pneus','Pneus',
      'Jours restants assurance','Assurance',
      'Jours restants visite technique','Visite technique',
      'Jours restants carte transport','Carte de transport',
      'Jours restants vignette','Vignette',
      'Âge (mois)','Commentaire',
    ];
    const data = this.vehiculesFiltres().map(v => [
      v.immatriculation, v.type_vehicule, v.marque, v.modele, v.annee,
      v.agence_nom ?? '', v.chauffeur_nom ?? '',
      v.kilometrage_actuel, v.disponible ? 'Oui' : 'Non', v.statut_display,
      v.km_prevu_revision ?? '', v.km_restant_revision ?? '', lib(v.statut_revision),
      v.km_prevu_pneus ?? '', v.km_restant_pneus ?? '', lib(v.statut_pneus),
      v.jr_assurance ?? '', lib(v.statut_assurance),
      v.jr_ct ?? '', lib(v.statut_ct),
      v.jr_carte_transport ?? '', lib(v.statut_carte_transport),
      v.jr_vignette ?? '', lib(v.statut_vignette),
      v.age_mois !== null ? Math.round(v.age_mois) : '', v.notes,
    ]);
    const cell = (x: any) => { const t = String(x ?? ''); return /[;"\r\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
    const csv  = '\uFEFF' + [hdrs, ...data].map(l => l.map(cell).join(';')).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `etat_parc_${new Date().toISOString().split('T')[0]}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
  }
}
