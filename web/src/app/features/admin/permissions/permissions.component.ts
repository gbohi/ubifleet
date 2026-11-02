// UbiFleet — Gestion des permissions par rôle (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { UserApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';

interface Droit { autorise: boolean; defaut: boolean; regle: boolean; }
interface PermMeta {
  roles:          { id: string; nom: string; niveau: number; is_system: boolean }[];
  modules:        { value: string; label: string }[];
  module_actions: Record<string, { value: string; label: string }[]>;
  /** Droits effectifs : rôle → module → action. */
  effectifs:      Record<string, Record<string, Record<string, Droit>>>;
}

@Component({
  selector: 'ubi-permissions',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './permissions.component.html',
  styleUrls: ['./permissions.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PermissionsComponent implements OnInit {
  private userApi = inject(UserApiService);

  meta         = signal<PermMeta | null>(null);
  loading      = signal(true);
  saving       = signal(false);
  success      = signal('');
  error        = signal('');
  metaError    = signal('');
  selectedRole = signal<string>('');
  /** Modifications en attente : « role::module::action » → valeur. */
  pending      = signal<Map<string, boolean>>(new Map());
  confirmReset = signal(false);

  roleCourant = computed(() => this.meta()?.roles.find(r => r.id === this.selectedRole()) ?? null);
  estSuperAdmin = computed(() => (this.roleCourant()?.niveau ?? 0) >= 10);
  modules = computed(() => (this.meta()?.modules ?? []).filter(m => (this.meta()?.module_actions[m.value] ?? []).length));
  nbPersonnalises = computed(() => {
    const e = this.meta()?.effectifs[this.selectedRole()];
    if (!e) return 0;
    return Object.values(e).reduce((n, acts) => n + Object.values(acts).filter(d => d.regle).length, 0);
  });

  get hasPending(): boolean { return this.pending().size > 0; }
  countPending(): number    { return this.pending().size; }

  private cle(module: string, action: string): string { return `${this.selectedRole()}::${module}::${action}`; }

  droit(module: string, action: string): Droit | null {
    return this.meta()?.effectifs[this.selectedRole()]?.[module]?.[action] ?? null;
  }

  isAllowed(module: string, action: string): boolean {
    const k = this.cle(module, action);
    if (this.pending().has(k)) return this.pending().get(k)!;
    return this.droit(module, action)?.autorise ?? false;
  }

  /** Valeur différente du droit par défaut du niveau (après modifications en attente). */
  estPersonnalise(module: string, action: string): boolean {
    const d = this.droit(module, action);
    return !!d && this.isAllowed(module, action) !== d.defaut;
  }

  estEnAttente(module: string, action: string): boolean { return this.pending().has(this.cle(module, action)); }

  compteModule(module: string): string {
    const acts = this.meta()?.module_actions[module] ?? [];
    return `${acts.filter(a => this.isAllowed(module, a.value)).length}/${acts.length}`;
  }

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.loading.set(true);
    this.metaError.set('');
    this.userApi.getPermissionsMeta().subscribe({
      next: (meta: PermMeta) => {
        this.meta.set(meta);
        if (!this.selectedRole() || !meta.roles.some(r => r.id === this.selectedRole())) {
          // Par défaut, le premier rôle réglable (le super admin a tous les droits)
          this.selectedRole.set((meta.roles.find(r => r.niveau < 10) ?? meta.roles[0])?.id ?? '');
        }
        this.loading.set(false);
      },
      error: (err: any) => {
        this.metaError.set(err?.status === 403
          ? 'Accès refusé — seul le super administrateur peut gérer les permissions.'
          : 'Impossible de charger les permissions.');
        this.loading.set(false);
      },
    });
  }

  selectRole(role: string): void {
    if (this.hasPending && !confirm('Des modifications ne sont pas enregistrées. Les abandonner ?')) return;
    this.selectedRole.set(role);
    this.pending.set(new Map());
    this.success.set(''); this.error.set(''); this.confirmReset.set(false);
  }

  private poser(map: Map<string, boolean>, module: string, action: string, valeur: boolean): void {
    const k = this.cle(module, action);
    // Retour à la valeur enregistrée : plus rien en attente
    if (valeur === (this.droit(module, action)?.autorise ?? false)) map.delete(k); else map.set(k, valeur);
  }

  toggle(module: string, action: string): void {
    if (this.estSuperAdmin()) return;
    const map = new Map(this.pending());
    this.poser(map, module, action, !this.isAllowed(module, action));
    this.pending.set(map);
    this.success.set('');
  }

  toggleModule(module: string, valeur: boolean): void {
    if (this.estSuperAdmin()) return;
    const map = new Map(this.pending());
    for (const a of this.meta()?.module_actions[module] ?? []) this.poser(map, module, a.value, valeur);
    this.pending.set(map);
    this.success.set('');
  }

  /** Remet les actions du module à leur valeur par défaut (dans les modifications en attente). */
  defautModule(module: string): void {
    if (this.estSuperAdmin()) return;
    const map = new Map(this.pending());
    for (const a of this.meta()?.module_actions[module] ?? []) {
      const d = this.droit(module, a.value);
      if (d) this.poser(map, module, a.value, d.defaut);
    }
    this.pending.set(map);
  }

  saveAll(): void {
    if (!this.hasPending || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    const bulk = Array.from(this.pending().entries()).map(([key, autorise]) => {
      const [role, module, action] = key.split('::');
      return { role, module, action, autorise };
    });
    this.userApi.bulkUpdatePermissions(bulk).subscribe({
      next: (res: any) => {
        this.saving.set(false);
        this.success.set(res.detail ?? 'Permissions enregistrées.');
        this.pending.set(new Map());
        this.charger();
      },
      error: (err: any) => {
        this.saving.set(false);
        this.error.set(messageErreurApi(err, 'Erreur lors de l\'enregistrement.'));
      },
    });
  }

  reinitialiserRole(): void {
    const r = this.roleCourant();
    if (!r) return;
    this.userApi.reinitialiserPermissions(r.id).subscribe({
      next: (res: any) => {
        this.confirmReset.set(false);
        this.pending.set(new Map());
        this.success.set(res.detail ?? 'Droits par défaut rétablis.');
        this.charger();
      },
      error: (err: any) => { this.confirmReset.set(false); this.error.set(messageErreurApi(err, 'Action impossible.')); },
    });
  }

  cancelPending(): void {
    this.pending.set(new Map());
    this.success.set('');
    this.error.set('');
  }
}
