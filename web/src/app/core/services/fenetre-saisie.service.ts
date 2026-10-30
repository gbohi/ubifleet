// UbiFleet — Fenêtre de saisie des pleins et des relevés kilométriques
//
// Bornes calculées par le serveur (date du jour du serveur, droit « Saisie
// hors délai » de l'utilisateur). Le calendrier n'est qu'un confort : le
// serveur refuse de toute façon une date hors fenêtre.
import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export type DomaineSaisie = 'carburant' | 'releves';

export interface FenetreSaisie {
  jours: number;            // 0 = désactivée
  active: boolean;
  date_min: string | null;  // AAAA-MM-JJ
  date_max: string;         // aujourd'hui (serveur)
  hors_delai: boolean;      // l'utilisateur peut saisir hors fenêtre
}

@Injectable({ providedIn: 'root' })
export class FenetreSaisieService {
  private http = inject(HttpClient);

  readonly fenetres = signal<Record<DomaineSaisie, FenetreSaisie> | null>(null);
  /** Écart entre l'horloge locale du serveur et celle de l'appareil (ms). */
  private readonly decalage = signal<number | null>(null);

  /** Recharge les bornes (à l'ouverture de chaque formulaire : la date du jour change). */
  charger(): void {
    this.http.get<Record<DomaineSaisie, FenetreSaisie> & { maintenant: string }>(
      `${environment.apiUrl}/parametrage/fenetre-saisie/`
    ).subscribe({
      next: ({ maintenant, ...f }) => {
        this.fenetres.set(f);
        // Heure locale du serveur lue comme UTC : on relira les champs UTC
        if (maintenant) this.decalage.set(Date.parse(maintenant + 'Z') - Date.now());
      },
      error: () => {},
    });
  }

  /** Heure actuelle du serveur (HH:MM), pour pré-remplir les saisies ; null tant qu'elle n'est pas connue. */
  heureServeur(): string | null {
    const d = this.decalage();
    if (d === null) return null;
    return new Date(Date.now() + d).toISOString().slice(11, 16);
  }

  fenetre(domaine: DomaineSaisie): FenetreSaisie | null {
    return this.fenetres()?.[domaine] ?? null;
  }

  /** Borne basse du calendrier : aucune si désactivée ou droit hors délai. */
  min(domaine: DomaineSaisie): string | null {
    const f = this.fenetre(domaine);
    return f && f.active && !f.hors_delai ? f.date_min : null;
  }

  /** Borne haute du calendrier : aujourd'hui (date du serveur). */
  max(domaine: DomaineSaisie): string | null {
    return this.fenetre(domaine)?.date_max ?? null;
  }

  /** Message d'erreur pour une date saisie, ou null si elle est acceptée. */
  erreur(domaine: DomaineSaisie, date: string | null | undefined): string | null {
    const f = this.fenetre(domaine);
    if (!f || !date) return null;
    if (date > f.date_max) return 'La date ne peut pas être dans le futur.';
    const min = this.min(domaine);
    if (min && date < min) {
      return `Date hors de la fenêtre de saisie (du ${fr(min)} au ${fr(f.date_max)}).`;
    }
    return null;
  }

  /** Saisie autorisée mais hors délai : elle sera tracée. */
  horsDelai(domaine: DomaineSaisie, date: string | null | undefined): boolean {
    const f = this.fenetre(domaine);
    return !!(f && date && f.active && f.hors_delai && f.date_min && date < f.date_min);
  }

  /** Texte d'aide sous le champ date. */
  aide(domaine: DomaineSaisie): string | null {
    const f = this.fenetre(domaine);
    if (!f?.active || !f.date_min) return null;
    return f.hors_delai
      ? `Fenêtre de saisie : du ${fr(f.date_min)} au ${fr(f.date_max)}. Vous pouvez saisir hors délai (ce sera tracé).`
      : `Dates acceptées : du ${fr(f.date_min)} au ${fr(f.date_max)}.`;
  }
}

/** Heure de l'appareil (HH:MM), en attendant celle du serveur. */
export function heureLocale(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function fr(d: string): string {
  const [a, m, j] = d.split('-');
  return `${j}/${m}/${a}`;
}

/** Message lisible d'une erreur d'API (detail, ou erreurs de champs). */
export function messageErreurApi(err: any, defaut: string): string {
  const e = err?.error;
  if (!e || typeof e !== 'object') return defaut;
  if (e.detail) return e.detail;
  const msgs = Object.values(e).flat().filter(m => typeof m === 'string');
  return msgs.length ? msgs.join(' ') : defaut;
}
