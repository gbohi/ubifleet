// UbiFleet — Gestion Utilisateurs (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal, computed
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { UserApiService, AgenceApiService, RoleApiService } from '../../../core/services/api.service';
import { messageErreurApi } from '../../../core/services/fenetre-saisie.service';
import { AuthService } from '../../../core/services/auth.service';
import { UbiUser, Role, Agence } from '../../../core/models';

@Component({
  selector: 'ubi-users',
  standalone: true,
  imports: [RouterLink, DatePipe, ReactiveFormsModule],
  templateUrl: './users.component.html',
  styleUrls: ['./users.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UsersComponent implements OnInit {
  private fb        = inject(FormBuilder);
  private userApi   = inject(UserApiService);
  private agenceApi = inject(AgenceApiService);
  private roleApi   = inject(RoleApiService);
  private auth      = inject(AuthService);

  // « Toutes les agences » n'est proposé qu'aux utilisateurs eux-mêmes sans agence
  peutChoisirToutesAgences = computed(() => !this.auth.currentUser()?.agence);

  users        = signal<UbiUser[]>([]);
  total        = signal(0);
  page         = signal(1);
  loading      = signal(true);
  agences      = signal<Agence[]>([]);
  rolesDb      = signal<Role[]>([]);

  searchVal    = signal('');
  filterRole   = signal('');
  filterActif  = signal('');
  filterAgence = signal('');
  private minuterie?: ReturnType<typeof setTimeout>;
  private minuterieMsg?: ReturnType<typeof setTimeout>;
  moi = computed(() => this.auth.currentUser());
  nbFiltresActifs = computed(() =>
    [this.searchVal(), this.filterRole(), this.filterActif(), this.filterAgence()].filter(v => !!v).length);

  showModal    = signal(false);
  editUserId   = signal<string | null>(null);
  saving       = signal(false);
  modalError   = signal('');
  modalSuccess = signal('');
  deleteUserId = signal<string | null>(null);

  showPwdModal = signal(false);
  pwdUserId    = signal<string | null>(null);
  pwdSaving    = signal(false);
  pwdError     = signal('');
  newPwd       = signal('');

  get roles(): { value: string; label: string }[] {
    return this.rolesDb().map(r => ({ value: r.id, label: r.nom }));
  }

  /** Rôles attribuables : actifs et de niveau inférieur au sien (tous pour le super admin). */
  rolesAttribuables = computed(() => {
    const monNiveau = (this.moi() as any)?.role_detail?.niveau ?? 0;
    return this.rolesDb()
      .filter(r => r.is_active && (monNiveau >= 10 || r.niveau < monNiveau))
      .sort((a, b) => b.niveau - a.niveau);
  });

  userForm = this.fb.group({
    email:      ['', [Validators.required, Validators.email]],
    username:   [''],
    first_name: ['', Validators.required],
    last_name:  ['', Validators.required],
    role:       ['' as string, Validators.required],
    agence:     ['' as string],
    telephone:  [''],
    password:   [''],
    password2:  [''],
  });

  get f() { return this.userForm.controls; }

  get totalPages(): number { return Math.ceil(this.total() / 20) || 1; }
  get pages(): number[] {
    const cur = this.page(), max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.loadUsers();
    this.roleApi.getAll().subscribe({
      next: (list) => this.rolesDb.set(list),
      error: () => {},
    });
    this.agenceApi.getAll().subscribe({
      next: (list: any) => this.agences.set(Array.isArray(list) ? list : (list.results ?? [])),
      error: () => {},
    });
  }

  loadUsers(): void {
    this.loading.set(true);
    const filters: Record<string, any> = { page: this.page() };
    if (this.searchVal())   filters['search']    = this.searchVal();
    if (this.filterRole())  filters['role']      = this.filterRole();
    if (this.filterActif()) filters['is_active'] = this.filterActif();
    if (this.filterAgence()) filters['agence']   = this.filterAgence();

    this.userApi.getAll(filters).subscribe({
      next: (res: any) => {
        this.users.set(res.results ?? []);
        this.total.set(res.count ?? 0);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onSearch(e: Event): void {
    const v = (e.target as HTMLInputElement).value.trim();
    clearTimeout(this.minuterie);
    this.minuterie = setTimeout(() => { this.searchVal.set(v); this.page.set(1); this.loadUsers(); }, 350);
  }
  onAgenceFilter(e: Event): void {
    this.filterAgence.set((e.target as HTMLSelectElement).value);
    this.page.set(1); this.loadUsers();
  }
  reinitialiserFiltres(): void {
    this.searchVal.set(''); this.filterRole.set(''); this.filterActif.set(''); this.filterAgence.set('');
    this.page.set(1); this.loadUsers();
  }
  private afficher(msg: string): void {
    this.modalSuccess.set(msg);
    clearTimeout(this.minuterieMsg);
    this.minuterieMsg = setTimeout(() => this.modalSuccess.set(''), 5000);
  }
  onRoleFilter(e: Event): void {
    this.filterRole.set((e.target as HTMLSelectElement).value);
    this.page.set(1); this.loadUsers();
  }
  onActifFilter(e: Event): void {
    this.filterActif.set((e.target as HTMLSelectElement).value);
    this.page.set(1); this.loadUsers();
  }

  openModal(user?: UbiUser): void {
    this.modalError.set('');
    this.modalSuccess.set('');
    if (user) {
      this.editUserId.set(user.id);
      this.userForm.patchValue({
        email:      user.email,
        username:   user.username,
        first_name: user.first_name,
        last_name:  user.last_name,
        role:       user.role ?? '',
        agence:     user.agence ?? '',
        telephone:  user.telephone,
        password:   '',
        password2:  '',
      });
      this.f['password'].clearValidators();
      this.f['password2'].clearValidators();
    } else {
      this.editUserId.set(null);
      // Rattaché à une agence : le nouveau compte est dans la même agence
      this.userForm.reset({ role: '', agence: this.peutChoisirToutesAgences() ? '' : ((this.moi() as any)?.agence ?? '') });
      this.f['password'].setValidators([Validators.required, Validators.minLength(8)]);
      this.f['password2'].setValidators([Validators.required]);
    }
    this.f['password'].updateValueAndValidity();
    this.f['password2'].updateValueAndValidity();
    this.showModal.set(true);
  }

  closeModal(): void { this.showModal.set(false); }

  saveUser(): void {
    this.userForm.markAllAsTouched();
    if (this.userForm.invalid || this.saving()) {
      if (this.userForm.invalid) this.modalError.set('Renseignez les champs obligatoires (*).');
      return;
    }
    const raw = this.userForm.value;

    if (!this.editUserId() && raw.password !== raw.password2) {
      this.modalError.set('Les mots de passe ne correspondent pas.');
      return;
    }

    this.saving.set(true);
    this.modalError.set('');

    const payload: Record<string, any> = {
      email:      (raw.email ?? '').trim(),
      first_name: (raw.first_name ?? '').trim(),
      last_name:  (raw.last_name ?? '').trim(),
      role:       raw.role || null,
      telephone:  raw.telephone ?? '',
      // Vide = « Toutes les agences » (contrôlé par le serveur)
      agence:     raw.agence || null,
    };
    if (raw.username?.trim()) payload['username'] = raw.username.trim();
    if (!this.editUserId()) {
      payload['password']  = raw.password;
      payload['password2'] = raw.password2;
    }

    const req = this.editUserId()
      ? this.userApi.update(this.editUserId()!, payload)
      : this.userApi.create(payload);

    req.subscribe({
      next: () => {
        this.saving.set(false);
        this.afficher(this.editUserId() ? 'Utilisateur modifié.' : 'Utilisateur créé.');
        this.closeModal();
        this.loadUsers();
      },
      error: (err) => {
        this.saving.set(false);
        this.modalError.set(messageErreurApi(err, "Erreur lors de l'enregistrement."));
      },
    });
  }

  actionErreur = signal('');

  toggleActive(user: UbiUser): void {
    this.actionErreur.set('');
    this.userApi.toggleActive(user.id).subscribe({
      next: (r: any) => { this.afficher(r?.detail ?? 'Statut modifié.'); this.loadUsers(); },
      error: err => this.actionErreur.set(messageErreurApi(err, 'Action impossible.')),
    });
  }

  confirmDelete(id: string): void { this.deleteUserId.set(id); }
  cancelDelete(): void             { this.deleteUserId.set(null); }

  doDelete(id: string): void {
    this.userApi.delete(id).subscribe({
      next: () => { this.deleteUserId.set(null); this.afficher('Utilisateur supprimé.'); this.loadUsers(); },
      error: err => { this.deleteUserId.set(null); this.actionErreur.set(messageErreurApi(err, 'Suppression impossible.')); },
    });
  }

  openPwdModal(user: UbiUser): void {
    this.pwdUserId.set(user.id);
    this.pwdError.set('');
    this.newPwd.set('');
    this.showPwdModal.set(true);
  }
  closePwdModal(): void { this.showPwdModal.set(false); }
  onNewPwd(e: Event): void { this.newPwd.set((e.target as HTMLInputElement).value); }

  submitResetPwd(): void {
    if (!this.newPwd() || this.newPwd().length < 8) {
      this.pwdError.set('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    this.pwdSaving.set(true);
    this.userApi.resetPassword(this.pwdUserId()!, this.newPwd()).subscribe({
      next: () => { this.pwdSaving.set(false); this.closePwdModal(); this.afficher('Mot de passe réinitialisé.'); },
      error: (err) => {
        this.pwdSaving.set(false);
        this.pwdError.set(messageErreurApi(err, 'Réinitialisation impossible.'));
      },
    });
  }

  estAttribuable(id: string): boolean { return this.rolesAttribuables().some(r => r.id === id); }
  nomRole(id: string): string { return this.rolesDb().find(r => r.id === id)?.nom ?? '—'; }

  nomUtilisateur(id: string | null): string {
    const u = this.users().find(x => x.id === id);
    return u ? `${u.first_name} ${u.last_name}`.trim() || u.email : '';
  }

  onPageChange(p: number): void { this.page.set(p); this.loadUsers(); }

  niveauBadgeClass(niveau: number | undefined | null): string {
    if (!niveau) return 'badge-gray';
    if (niveau >= 10) return 'badge-danger';
    if (niveau >= 8)  return 'badge-navy';
    if (niveau >= 6)  return 'badge-info';
    if (niveau >= 4)  return 'badge-warning';
    if (niveau >= 3)  return 'badge-green';
    return 'badge-gray';
  }
}
