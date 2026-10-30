// UbiFleet — Types de mouvement des relevés et des prises de carburant (référentiel paramétrable)
import { Injectable, computed, inject, signal } from '@angular/core';
import { ParametrageApiService } from './api.service';

export interface TypeMouvementRef {
  id: number;
  code: string;
  libelle: string;
  couleur: 'green' | 'orange' | 'blue' | 'red' | 'gray';
  reserve?: boolean;     // type « tournée » : ni supprimable ni recodable
  actif: boolean;
  pour_releves: boolean;  // proposé dans les relevés kilométriques
  pour_prises: boolean;   // proposé dans les prises de carburant
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
  /** Types proposés à la saisie d'un relevé. */
  actifs = computed(() => this.tous().filter(t => t.actif && t.pour_releves));
  /** Types proposés à la saisie d'une prise de carburant. */
  pourPrises = computed(() => this.tous().filter(t => t.actif && t.pour_prises));

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

  couleur(code: string | null | undefined): string {
    return this.trouver(code)?.couleur ?? 'gray';
  }

  classeBadge(code: string | null | undefined): string {
    return CLASSE_BADGE[this.trouver(code)?.couleur ?? 'gray'] ?? 'badge-gray';
  }
}
