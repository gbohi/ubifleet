// UbiFleet — Gestion des permissions par rôle (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { UserApiService, RoleApiService } from '../../../core/services/api.service';
import { Role } from '../../../core/models';

interface PermMeta {
  roles:          any[];
  modules:        { value: string; label: string }[];
  actions:        { value: string; label: string }[];
  module_actions: Record<string, { value: string; label: string }[]>;
}

interface PermRule {
  id?:      string;
  role:     string;
  module:   string;
  action:   string;
  autorise: boolean;
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
  private roleApi = inject(RoleApiService);

  meta        = signal<PermMeta | null>(null);
  rules       = signal<PermRule[]>([]);
  rolesDb     = signal<Role[]>([]);
  loading     = signal(true);
  saving      = signal(false);
  success     = signal('');
  error       = signal('');
  metaError   = signal('');
  selectedRole= signal<string>('');
  pending     = signal<Map<string, boolean>>(new Map());

  moduleKeys = computed((): string[] => {
    const meta = this.meta();
    if (!meta) return [];
    return meta.modules.map(m => m.value);
  });

  get roles(): { value: string; label: string }[] {
    return this.rolesDb().map((r: Role) => ({ value: r.id, label: r.nom }));
  }

  get hasPending(): boolean { return this.pending().size > 0; }
  countPending(): number    { return this.pending().size; }

  getModuleLabel(module: string): string {
    return this.meta()?.modules.find(m => m.value === module)?.label ?? module;
  }

  getRoleLabel(roleId: string): string {
    return this.rolesDb().find((r: Role) => r.id === roleId)?.nom ?? roleId;
  }

  getActionsForModule(module: string): { value: string; label: string }[] {
    const meta = this.meta();
    if (!meta) return [];
    return meta.module_actions?.[module] ?? meta.actions;
  }

  isAllowed(role: string, module: string, action: string): boolean {
    const key = `${role}::${module}::${action}`;
    if (this.pending().has(key)) return this.pending().get(key)!;
    const rule = this.rules().find(
      r => r.role === role && r.module === module && r.action === action
    );
    return rule?.autorise ?? false;
  }

  ngOnInit(): void {
    this.roleApi.getAll().subscribe({
      next: (list: Role[]) => {
        this.rolesDb.set(list);
        if (list.length > 0 && !this.selectedRole()) {
          const sorted = [...list].sort((a, b) => b.niveau - a.niveau);
          this.selectedRole.set(sorted[0].id);
        }
        this.loadAll();
      },
      error: () => this.loadAll(),
    });
  }

  loadAll(): void {
    this.loading.set(true);
    this.metaError.set('');
    let metaDone = false, rulesDone = false;
    const checkDone = () => { if (metaDone && rulesDone) this.loading.set(false); };

    this.userApi.getPermissionsMeta().subscribe({
      next: (meta: PermMeta) => { this.meta.set(meta); metaDone = true; checkDone(); },
      error: (err: any) => {
        this.metaError.set(
          err?.status === 403
            ? 'Accès refusé — seul le super administrateur peut gérer les permissions.'
            : 'Impossible de charger les métadonnées.'
        );
        metaDone = true; checkDone();
      },
    });

    // Charger TOUTES les permissions sans limite de page
    // (page_size=1000 accepté grâce à UbiFleetPagination)
    this.userApi.getPermissions({ page_size: 1000 }).subscribe({
      next: (res: any) => {
        const list = Array.isArray(res) ? res : (res.results ?? []);
        this.rules.set(list);
        rulesDone = true; checkDone();
      },
      error: () => { rulesDone = true; checkDone(); },
    });
  }

  selectRole(role: string): void {
    this.selectedRole.set(role);
    this.pending.set(new Map());
    this.success.set('');
    this.error.set('');
  }

  toggle(module: string, action: string): void {
    const role    = this.selectedRole();
    const key     = `${role}::${module}::${action}`;
    const current = this.isAllowed(role, module, action);
    const map     = new Map(this.pending());
    map.set(key, !current);
    this.pending.set(map);
    this.success.set('');
  }

  toggleModule(module: string, forceValue?: boolean): void {
    const role    = this.selectedRole();
    const actions = this.getActionsForModule(module);
    const map     = new Map(this.pending());
    const allAllowed = actions.every(a => this.isAllowed(role, module, a.value));
    const newValue   = forceValue !== undefined ? forceValue : !allAllowed;
    for (const action of actions) {
      map.set(`${role}::${module}::${action.value}`, newValue);
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
        this.success.set(res.detail ?? 'Permissions sauvegardées.');
        this.pending.set(new Map());
        this.loadAll();
      },
      error: (err: any) => {
        this.saving.set(false);
        this.error.set(err?.error?.detail ?? 'Erreur lors de la sauvegarde.');
      },
    });
  }

  cancelPending(): void {
    this.pending.set(new Map());
    this.success.set('');
    this.error.set('');
  }
}
