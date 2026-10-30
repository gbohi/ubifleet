// UbiFleet — Paramètres › Règles & seuils › Fenêtre de saisie
//
// Nombre de jours pendant lesquels un plein ou un relevé kilométrique peut
// être saisi (aujourd'hui, J-1, …) ; au-delà, la donnée est figée.
// 0 = fenêtre désactivée. Exception : droit « Saisie hors délai » (Permissions).
import {
  Component, ChangeDetectionStrategy, OnInit, computed, inject, input, signal,
} from '@angular/core';
import { ParametrageApiService } from '../../../core/services/api.service';
import { DomaineSaisie, FenetreSaisieService } from '../../../core/services/fenetre-saisie.service';

interface Domaine { code: DomaineSaisie; cle: string; titre: string; icone: string; donnees: string; }

const DOMAINES: Domaine[] = [
  { code: 'carburant', cle: 'fenetre_saisie_carburant_jours', titre: 'Prises de carburant',
    icone: 'fas fa-gas-pump', donnees: 'pleins' },
  { code: 'releves', cle: 'fenetre_saisie_releves_jours', titre: 'Relevés kilométriques',
    icone: 'fas fa-tachometer-alt', donnees: 'relevés' },
];
const JOURS_DEFAUT = 3;
const JOURS_MAX = 365;
const APERCU = 7;

@Component({
  selector: 'ubi-param-fenetre-saisie',
  standalone: true,
  templateUrl: './fenetre-saisie.component.html',
  styleUrls: ['./fenetre-saisie.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FenetreSaisieComponent implements OnInit {
  private api      = inject(ParametrageApiService);
  private fenetres = inject(FenetreSaisieService);

  ecriture = input(false);

  readonly domaines = DOMAINES;
  readonly joursMax = JOURS_MAX;

  valeurs    = signal<Record<string, number>>({});
  initiales  = signal<Record<string, number>>({});
  chargement = signal(true);
  enregistrement = signal(false);
  notice     = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);

  modifiees = computed(() => {
    const v = this.valeurs(), init = this.initiales();
    return Object.keys(v).filter(k => v[k] !== init[k]);
  });
  invalides = computed(() => {
    const v = this.valeurs();
    return Object.keys(v).filter(k => !Number.isInteger(v[k]) || v[k] < 0 || v[k] > JOURS_MAX);
  });

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.chargement.set(true);
    this.api.getAll().subscribe({
      next: list => {
        const vals: Record<string, number> = {};
        DOMAINES.forEach(d => {
          const p = list.find((x: any) => x.cle === d.cle);
          vals[d.cle] = p ? Number(p.valeur) || 0 : 0;
        });
        this.initiales.set(vals);
        this.valeurs.set({ ...vals });
        this.chargement.set(false);
      },
      error: () => {
        this.chargement.set(false);
        this.notice.set({ type: 'err', texte: 'Impossible de charger les paramètres.' });
      },
    });
  }

  jours(d: Domaine): number { return this.valeurs()[d.cle] ?? 0; }
  active(d: Domaine): boolean { return this.jours(d) > 0; }
  modifie(d: Domaine): boolean { return this.modifiees().includes(d.cle); }
  invalide(d: Domaine): boolean { return this.invalides().includes(d.cle); }

  basculer(d: Domaine): void {
    const init = this.initiales()[d.cle];
    this.fixer(d, this.active(d) ? 0 : (init > 0 ? init : JOURS_DEFAUT));
  }

  saisir(d: Domaine, e: Event): void {
    const v = (e.target as HTMLInputElement).valueAsNumber;
    this.fixer(d, Number.isNaN(v) ? -1 : v);
  }

  private fixer(d: Domaine, v: number): void {
    this.valeurs.update(x => ({ ...x, [d.cle]: v }));
  }

  /** Les derniers jours, du plus ancien à aujourd'hui, avec leur état. */
  apercu(d: Domaine): { libelle: string; jour: string; ouvert: boolean }[] {
    const n = this.jours(d);
    const total = Math.max(APERCU, Math.min(n + 2, 14));
    return Array.from({ length: total }, (_, i) => {
      const ecart = total - 1 - i;
      const date = new Date();
      date.setDate(date.getDate() - ecart);
      return {
        libelle: ecart === 0 ? "Auj." : `J-${ecart}`,
        jour: date.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit' }),
        ouvert: n <= 0 || ecart < n,
      };
    });
  }

  resume(d: Domaine): string {
    const n = this.jours(d);
    if (n <= 0) return `Toutes les dates passées sont acceptées ; les ${d.donnees} restent modifiables à tout moment.`;
    const jours = n === 1 ? "aujourd'hui uniquement"
      : n === 2 ? "aujourd'hui et la veille (J-1)"
      : `aujourd'hui et les ${n - 1} jours précédents (jusqu'à J-${n - 1})`;
    return `Saisie acceptée pour ${jours}. Passé ce délai, les ${d.donnees} sont figés : ni modification ni suppression.`;
  }

  annuler(): void {
    this.valeurs.set({ ...this.initiales() });
    this.notice.set(null);
  }

  enregistrer(): void {
    if (this.invalides().length || this.enregistrement()) return;
    const items = this.modifiees().map(cle => ({ cle, valeur: String(this.valeurs()[cle]) }));
    if (!items.length) return;
    this.enregistrement.set(true);
    this.notice.set(null);
    this.api.bulkUpdate(items).subscribe({
      next: () => {
        this.enregistrement.set(false);
        this.notice.set({ type: 'ok', texte: 'Fenêtres de saisie enregistrées. Elles s’appliquent immédiatement.' });
        this.fenetres.charger();
        this.charger();
      },
      error: (err: any) => {
        this.enregistrement.set(false);
        this.notice.set({ type: 'err', texte: err?.error?.detail ?? "Erreur lors de l'enregistrement." });
      },
    });
  }
}
