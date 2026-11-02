// UbiFleet — Alertes Component (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AlertesStore } from '../../store/alertes/alertes.store';
import { Alerte } from '../../core/models';

@Component({
  selector: 'ubi-alertes',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './alertes.component.html',
  styleUrls: ['./alertes.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AlertesComponent implements OnInit {
  store = inject(AlertesStore);
  Math  = Math;

  // Modale traiter
  alerteEnTraitement = signal<Alerte | null>(null);
  notesTraitement    = signal('');
  traitementLoading  = signal(false);

  ngOnInit(): void {
    this.store.genererAlertes();
    this.store.loadResume();
    this.store.loadAlertes();
  }

  // ── Helpers badge ────────────────────────────────────────────────
  prioriteBadge(p: string): string {
    const map: Record<string, string> = {
      critique: 'badge-critique',
      haute:    'badge-haute',
      normale:  'badge-normale',
      basse:    'badge-basse',
    };
    return map[p] ?? 'badge-gray';
  }

  statutBadge(s: string): string {
    const map: Record<string, string> = {
      active:  'badge-danger',
      lue:     'badge-warning',
      traitee: 'badge-green',
      ignoree: 'badge-gray',
    };
    return map[s] ?? 'badge-gray';
  }

  typeIcon(t: string): string {
    const map: Record<string, string> = {
      revision_due:          'fas fa-tools',
      assurance_exp:         'fas fa-shield-alt',
      assurance_expiree:     'fas fa-shield-alt',
      conso_anormale:        'fas fa-gas-pump',
      ct_exp:                'fas fa-clipboard-check',
      ct_expiree:            'fas fa-clipboard-check',
      permis_exp:            'fas fa-id-card',
      permis_expire:         'fas fa-id-card',
      visite_med_exp:        'fas fa-notes-medical',
      visite_med_expiree:    'fas fa-notes-medical',
      contrat_exp:           'fas fa-file-signature',
      contrat_expire:        'fas fa-file-signature',
      tournee_ouverte:       'fas fa-route',
      budget_depasse:        'fas fa-coins',
      pneu_usure:            'fas fa-circle-notch',
      plein_anomalie:        'fas fa-exclamation-triangle',
      sinistre_ouvert:       'fas fa-car-crash',
      carte_transport_exp:   'fas fa-file-alt',
      carte_transport_expiree:'fas fa-file-alt',
      vignette_exp:          'fas fa-tag',
      vignette_expiree:      'fas fa-tag',
    };
    return map[t] ?? 'fas fa-bell';
  }

  // ── Filtres ──────────────────────────────────────────────────────
  onFilter(key: 'statut' | 'priorite' | 'type_alerte' | 'agence', e: Event): void {
    const val = (e.target as HTMLSelectElement).value;
    this.store.setFilter(key, val);
    this.store.loadAlertes();
  }

  // ── Actions ──────────────────────────────────────────────────────
  ouvrirTraitement(a: Alerte): void {
    this.alerteEnTraitement.set(a);
    this.notesTraitement.set('');
  }

  fermerTraitement(): void {
    this.alerteEnTraitement.set(null);
  }

  confirmerTraitement(): void {
    const a = this.alerteEnTraitement();
    if (!a) return;
    this.traitementLoading.set(true);
    this.store.traiterAlerte({ id: a.id, notes: this.notesTraitement() });
    setTimeout(() => {
      this.traitementLoading.set(false);
      this.fermerTraitement();
      this.store.loadResume();
    }, 600);
  }

  ignorer(a: Alerte): void {
    this.store.ignorerAlerte(a.id);
  }

  genererEtRecharger(): void {
    this.store.genererAlertes();
    setTimeout(() => {
      this.store.loadResume();
      this.store.loadAlertes();
    }, 800);
  }

  marquerToutesLues(): void {
    this.store.marquerToutesLues();
    setTimeout(() => this.store.loadResume(), 400);
  }

  onNotesInput(e: Event): void {
    this.notesTraitement.set((e.target as HTMLTextAreaElement).value);
  }
}
