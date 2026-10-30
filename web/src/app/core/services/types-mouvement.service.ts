// UbiFleet — Types de mouvement des relevés kilométriques (référentiel paramétrable)
import { Injectable, computed, inject, signal } from '@angular/core';
import { ParametrageApiService } from './api.service';

export interface TypeMouvementRef {
  id: number;
  code: string;
  libelle: string;
  couleur: 'green' | 'orange' | 'blue' | 'red' | 'gray';
  avec_tournee: boolean;
  actif: boolean;
}

const CLASSE_BADGE: Record<string, string> = {
  green: 'badge-green', orange: 'badge-warning', blue: 'badge-info', red: 'badge-danger', gray: 'badge-gray',
};

/** Cache partagé des types de mouvement, chargé une fois par session. */
@Injectable({ providedIn: 'root' })
export class TypesMouvementService {
  private api = inject(ParametrageApiService);
  private charge = false;

  tous   = signal<TypeMouvementRef[]>([]);
  /** Types proposés à la saisie. */
  actifs = computed(() => this.tous().filter(t => t.actif));

  charger(forcer = false): void {
    if (this.charge && !forcer) return;
    this.charge = true;
    this.api.getTypesMouvement().subscribe({
      next: l => this.tous.set(l),
      error: () => { this.charge = false; },
    });
  }

  private trouver(code: string | null | undefined): TypeMouvementRef | undefined {
    return this.tous().find(t => t.code === code);
  }

  libelle(code: string | null | undefined): string {
    return this.trouver(code)?.libelle ?? code ?? '';
  }

  classeBadge(code: string | null | undefined): string {
    return CLASSE_BADGE[this.trouver(code)?.couleur ?? 'gray'] ?? 'badge-gray';
  }

  /** Le type demande-t-il une tournée / destination ? */
  avecTournee(code: string | null | undefined): boolean {
    return !!this.trouver(code)?.avec_tournee;
  }
}
