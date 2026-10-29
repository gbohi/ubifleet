// UbiFleet — Gestion des Rôles (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { RoleApiService } from '../../../core/services/api.service';
import { Role } from '../../../core/models';

@Component({
  selector: 'ubi-roles',
  standalone: true,
  imports: [RouterLink, DatePipe, ReactiveFormsModule],
  templateUrl: './roles.component.html',
  styleUrls: ['./roles.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RolesComponent implements OnInit {
  private fb      = inject(FormBuilder);
  private roleApi = inject(RoleApiService);

  roles       = signal<Role[]>([]);
  loading     = signal(true);
  showModal   = signal(false);
  editRoleId  = signal<string | null>(null);
  saving      = signal(false);
  modalError  = signal('');
  modalSuccess= signal('');
  deleteId    = signal<string | null>(null);
  deleteError = signal('');

  roleForm = this.fb.group({
    code:        ['', [Validators.required, Validators.pattern(/^[a-z0-9_]+$/)]],
    nom:         ['', Validators.required],
    niveau:      [2, [Validators.required, Validators.min(1), Validators.max(9)]],
    description: [''],
    is_active:   [true],
  });

  get f() { return this.roleForm.controls; }

  ngOnInit(): void { this.loadRoles(); }

  loadRoles(): void {
    this.loading.set(true);
    this.roleApi.getAll().subscribe({
      next: (list) => { this.roles.set(list); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  openModal(role?: Role): void {
    this.modalError.set('');
    this.modalSuccess.set('');
    if (role) {
      this.editRoleId.set(role.id);
      this.roleForm.patchValue({
        code: role.code, nom: role.nom,
        niveau: role.niveau, description: role.description,
        is_active: role.is_active,
      });
      // Code non modifiable après création
      this.f['code'].disable();
    } else {
      this.editRoleId.set(null);
      this.roleForm.reset({ niveau: 2, is_active: true });
      this.f['code'].enable();
    }
    this.showModal.set(true);
  }

  closeModal(): void { this.showModal.set(false); }

  saveRole(): void {
    if (this.roleForm.invalid || this.saving()) return;
    this.saving.set(true);
    this.modalError.set('');

    const raw = this.roleForm.getRawValue();
    const payload = {
      code: raw.code ?? '', nom: raw.nom ?? '',
      niveau: raw.niveau ?? 2, description: raw.description ?? '',
      is_active: raw.is_active ?? true,
    };

    const req = this.editRoleId()
      ? this.roleApi.update(this.editRoleId()!, payload)
      : this.roleApi.create(payload);

    req.subscribe({
      next: () => {
        this.saving.set(false);
        this.modalSuccess.set(this.editRoleId() ? 'Rôle modifié.' : 'Rôle créé.');
        this.closeModal();
        this.loadRoles();
      },
      error: (err) => {
        this.saving.set(false);
        if (err?.error && typeof err.error === 'object') {
          const msgs = Object.entries(err.error)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ');
          this.modalError.set(msgs);
        } else {
          this.modalError.set("Erreur lors de l'enregistrement.");
        }
      },
    });
  }

  confirmDelete(id: string): void {
    this.deleteId.set(id);
    this.deleteError.set('');
  }
  cancelDelete(): void { this.deleteId.set(null); }

  doDelete(id: string): void {
    this.roleApi.delete(id).subscribe({
      next: () => { this.deleteId.set(null); this.loadRoles(); },
      error: (err) => {
        this.deleteError.set(err?.error?.detail ?? "Impossible de supprimer ce rôle.");
      },
    });
  }

  niveauLabel(n: number): string {
    if (n >= 10) return 'Super Admin';
    if (n >= 8)  return 'Direction';
    if (n >= 6)  return 'Responsable';
    if (n >= 4)  return 'Gestionnaire';
    if (n >= 3)  return 'Comptable';
    if (n >= 2)  return 'Opérateur';
    return 'Chauffeur';
  }

  niveauClass(n: number): string {
    if (n >= 10) return 'badge-danger';
    if (n >= 8)  return 'badge-navy';
    if (n >= 6)  return 'badge-info';
    if (n >= 4)  return 'badge-warning';
    if (n >= 3)  return 'badge-green';
    return 'badge-gray';
  }
}
