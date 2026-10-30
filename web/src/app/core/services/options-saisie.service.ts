// UbiFleet — Listes des formulaires de saisie (pleins, relevés kilométriques)
//
// Options des listes avec recherche : véhicule (immatriculation), chauffeur
// (matricule et nom), tournée (code et libellé). Le serveur ne renvoie que
// les données de l'agence de l'utilisateur.
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { ChauffeurApiService, ParametrageApiService, VehiculeApiService } from './api.service';
import { OptionRecherche } from '../../shared/select-recherche/select-recherche.component';

export interface OptionVehicule extends OptionRecherche { value: string; agence: string | null; km: number; }
export interface OptionTournee extends OptionRecherche { value: number; agence: string | null; }

const liste = (res: any): any[] => Array.isArray(res) ? res : (res?.results ?? []);

@Injectable({ providedIn: 'root' })
export class OptionsSaisieService {
  private vehiculeApi    = inject(VehiculeApiService);
  private chauffeurApi   = inject(ChauffeurApiService);
  private parametrageApi = inject(ParametrageApiService);

  vehicules(): Observable<OptionVehicule[]> {
    return this.vehiculeApi.getAll({ page_size: 1000, ordering: 'immatriculation' }).pipe(map(res =>
      liste(res).map((v: any) => ({
        value: v.id, label: v.immatriculation, agence: v.agence ?? null, km: v.kilometrage_actuel ?? 0,
      }))));
  }

  chauffeurs(): Observable<OptionRecherche[]> {
    return this.chauffeurApi.getAll({ page_size: 1000, statut: 'actif' }).pipe(map(res =>
      liste(res).map((c: any) => ({
        value: c.id,
        label: [c.matricule, c.nom_complet || `${c.prenom ?? ''} ${c.nom ?? ''}`.trim()].filter(Boolean).join(' — '),
      }))));
  }

  tournees(): Observable<OptionTournee[]> {
    return this.parametrageApi.getTournees({ actif: true }).pipe(map(l =>
      liste(l).map((t: any) => ({
        value: t.id, label: `${t.code} — ${t.libelle}`, detail: t.agence_nom ?? undefined, agence: t.agence ?? null,
      }))));
  }
}

/** Tournées de l'agence du véhicule (toutes si le véhicule ou l'agence n'est pas connu). */
export function tourneesDuVehicule(tournees: OptionTournee[], agence: string | null | undefined): OptionTournee[] {
  if (!agence) return tournees;
  const memeAgence = tournees.filter(t => t.agence === agence);
  return memeAgence.length ? memeAgence : tournees;
}
