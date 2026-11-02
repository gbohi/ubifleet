// UbiFleet — Alertes Component (Angular 18)
import {
  Component, inject, OnInit, OnDestroy,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AlertesStore } from '../../store/alertes/alertes.store';
import { AgenceApiService, AlerteApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { messageErreurApi } from '../../core/services/fenetre-saisie.service';
import { Alerte } from '../../core/models';

/** Lien vers l'écran où l'alerte se règle. */
interface LienAlerte { libelle: string; icone: string; route: any[]; }

@Component({
  selector: 'ubi-alertes',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './alertes.component.html',
  styleUrls: ['./alertes.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AlertesComponent implements OnInit, OnDestroy {
  store = inject(AlertesStore);
  private api = inject(AlerteApiService);
  private agenceApi = inject(AgenceApiService);
  private auth = inject(AuthService);
  Math  = Math;

  readonly peutGenerer = this.auth.peutAcceder('alertes_generer');
  types    = signal<{ code: string; libelle: string }[]>([]);
  agences  = signal<{ id: string; nom: string }[]>([]);
  generation = signal(false);
  message  = signal('');
  erreur   = signal('');
  private minuterie?: ReturnType<typeof setTimeout>;
  private minuterieMsg?: ReturnType<typeof setTimeout>;

  nbFiltresActifs = computed(() => {
    const f = this.store.filters();
    return [f.statut !== 'a_traiter' ? f.statut || 'toutes' : '', f.priorite, f.type_alerte, f.agence, f.search]
      .filter(v => !!v).length;
  });

  // Modale traiter
  alerteEnTraitement = signal<Alerte | null>(null);
  notesTraitement    = signal('');
  traitementLoading  = signal(false);

  ngOnInit(): void {
    this.api.getTypes().subscribe({ next: t => this.types.set(t), error: () => {} });
    this.agenceApi.getAll().subscribe({
      next: (r: any) => this.agences.set(Array.isArray(r) ? r : r?.results ?? []), error: () => {},
    });
    // Vérification des échéances avant d'afficher la liste (profils autorisés)
    if (this.peutGenerer) this.generer(false);
    else this.recharger();
  }

  ngOnDestroy(): void { clearTimeout(this.minuterie); clearTimeout(this.minuterieMsg); }

  recharger(): void {
    this.store.loadResume();
    this.store.loadAlertes();
  }

  private afficher(msg: string): void {
    this.message.set(msg);
    clearTimeout(this.minuterieMsg);
    this.minuterieMsg = setTimeout(() => this.message.set(''), 5000);
  }

  // ── Helpers badge ────────────────────────────────────────────────
  prioriteBadge(p: string): string {
    const map: Record<string, string> = {
      critique: 'badge-critique', haute: 'badge-haute', normale: 'badge-normale', basse: 'badge-basse',
    };
    return map[p] ?? 'badge-gray';
  }

  statutBadge(s: string): string {
    const map: Record<string, string> = {
      active: 'badge-danger', lue: 'badge-warning', traitee: 'badge-green', ignoree: 'badge-gray',
    };
    return map[s] ?? 'badge-gray';
  }

  typeIcon(t: string): string {
    const map: Record<string, string> = {
      revision_due: 'fas fa-tools', assurance_exp: 'fas fa-shield-alt', assurance_expiree: 'fas fa-shield-alt',
      conso_anormale: 'fas fa-gas-pump', ct_exp: 'fas fa-clipboard-check', ct_expiree: 'fas fa-clipboard-check',
      permis_exp: 'fas fa-id-card', permis_expire: 'fas fa-id-card',
      visite_med_exp: 'fas fa-notes-medical', visite_med_expiree: 'fas fa-notes-medical',
      contrat_exp: 'fas fa-file-signature', contrat_expire: 'fas fa-file-signature',
      tournee_ouverte: 'fas fa-route', budget_depasse: 'fas fa-coins', pneu_usure: 'fas fa-circle-notch',
      plein_anomalie: 'fas fa-exclamation-triangle', sinistre_ouvert: 'fas fa-car-crash',
      carte_transport_exp: 'fas fa-file-alt', carte_transport_expiree: 'fas fa-file-alt',
      vignette_exp: 'fas fa-tag', vignette_expiree: 'fas fa-tag',
      demande_a_valider: 'fas fa-file-signature', controle_non_conforme: 'fas fa-clipboard-list',
    };
    return map[t] ?? 'fas fa-bell';
  }

  /** Écran où l'alerte se règle (prise de carburant, demande, contrôle…). */
  lien(a: Alerte): LienAlerte | null {
    const x = a as any;
    if (x.plein) return { libelle: 'Voir la prise de carburant', icone: 'fas fa-gas-pump', route: ['/carburant', x.plein, 'modifier'] };
    switch (a.type_alerte as string) {
      case 'demande_a_valider': return { libelle: 'Demandes à valider', icone: 'fas fa-file-signature', route: ['/demandes'] };
      case 'controle_non_conforme': return { libelle: 'Contrôles du véhicule', icone: 'fas fa-clipboard-check', route: ['/controle'] };
      case 'sinistre_ouvert': return { libelle: 'Sinistres', icone: 'fas fa-car-crash', route: ['/sinistres'] };
      case 'tournee_ouverte': return { libelle: 'Suivi des tournées', icone: 'fas fa-route', route: ['/carburant'] };
      case 'budget_depasse': return { libelle: 'Budget', icone: 'fas fa-coins', route: ['/budget'] };
      case 'revision_due': case 'pneu_usure': return { libelle: 'Entretiens', icone: 'fas fa-wrench', route: ['/entretien'] };
    }
    return null;
  }

  // ── Filtres ──────────────────────────────────────────────────────
  onFilter(key: 'statut' | 'priorite' | 'type_alerte' | 'agence' | 'search', e: Event): void {
    const val = (e.target as HTMLSelectElement | HTMLInputElement).value;
    clearTimeout(this.minuterie);
    const appliquer = () => { this.store.setFilter(key, val.trim()); this.store.loadAlertes(); };
    if (key === 'search') this.minuterie = setTimeout(appliquer, 350); else appliquer();
  }

  filtrerPriorite(p: string): void {
    const f = this.store.filters();
    const actif = f.priorite === p && f.statut === 'a_traiter';
    this.store.setFilter('statut', 'a_traiter');
    this.store.setFilter('priorite', actif ? '' : p);
    this.store.loadAlertes();
  }

  filtrerNonLues(): void {
    const actif = this.store.filters().statut === 'active';
    this.store.setFilter('statut', actif ? 'a_traiter' : 'active');
    this.store.setFilter('priorite', '');
    this.store.loadAlertes();
  }

  reinitialiser(): void {
    this.store.resetFilters();
    this.store.loadAlertes();
  }

  allerPage(p: number): void { this.store.setPage(p); this.store.loadAlertes(); }

  // ── Actions ──────────────────────────────────────────────────────
  ouvrirTraitement(a: Alerte): void {
    this.alerteEnTraitement.set(a);
    this.notesTraitement.set('');
    this.erreur.set('');
  }

  fermerTraitement(): void {
    if (!this.traitementLoading()) this.alerteEnTraitement.set(null);
  }

  confirmerTraitement(): void {
    const a = this.alerteEnTraitement();
    if (!a || this.traitementLoading()) return;
    this.traitementLoading.set(true);
    this.api.traiter(a.id, this.notesTraitement().trim()).subscribe({
      next: () => {
        this.traitementLoading.set(false);
        this.alerteEnTraitement.set(null);
        this.afficher(`Alerte « ${a.titre} » traitée.`);
        this.recharger();
      },
      error: err => {
        this.traitementLoading.set(false);
        this.erreur.set(messageErreurApi(err, 'Traitement impossible.'));
      },
    });
  }

  ignorer(a: Alerte): void {
    this.erreur.set('');
    this.api.ignorer(a.id).subscribe({
      next: () => { this.afficher(`Alerte « ${a.titre} » ignorée.`); this.recharger(); },
      error: err => this.erreur.set(messageErreurApi(err, "Impossible d'ignorer l'alerte.")),
    });
  }

  /** Vérifie toutes les échéances (documents, révisions, pneus…) puis recharge. */
  generer(avecMessage = true): void {
    if (this.generation()) return;
    this.generation.set(true);
    this.api.generer().subscribe({
      next: () => {
        this.generation.set(false);
        if (avecMessage) this.afficher('Échéances vérifiées : les alertes sont à jour.');
        this.recharger();
      },
      error: err => {
        this.generation.set(false);
        if (avecMessage) this.erreur.set(messageErreurApi(err, 'Vérification impossible.'));
        this.recharger();
      },
    });
  }

  marquerToutesLues(): void {
    this.api.marquerToutesLues().subscribe({
      next: (r: any) => { this.afficher(r?.detail ?? 'Alertes marquées comme lues.'); this.recharger(); },
      error: err => this.erreur.set(messageErreurApi(err, 'Action impossible.')),
    });
  }

  onNotesInput(e: Event): void {
    this.notesTraitement.set((e.target as HTMLTextAreaElement).value);
  }
}
