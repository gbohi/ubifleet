// UbiFleet — Mon Profil (Angular 18)
import {
  Component, inject, OnInit,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { UserApiService } from '../../core/services/api.service';
import { UbiUser } from '../../core/models';

@Component({
  selector: 'ubi-profil',
  standalone: true,
  imports: [RouterLink, DatePipe, ReactiveFormsModule],
  templateUrl: './profil.component.html',
  styleUrls: ['./profil.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfilComponent implements OnInit {
  private fb      = inject(FormBuilder);
  private userApi = inject(UserApiService);

  user        = signal<UbiUser | null>(null);
  loading     = signal(true);
  activeTab   = signal<'infos' | 'securite'>('infos');

  // Onglet infos
  infoSaving  = signal(false);
  infoSuccess = signal('');
  infoError   = signal('');

  infoForm = this.fb.group({
    first_name: ['', Validators.required],
    last_name:  ['', Validators.required],
    username:   ['', Validators.required],
    telephone:  [''],
  });

  get inf() { return this.infoForm.controls; }

  // Onglet sécurité
  pwdSaving  = signal(false);
  pwdSuccess = signal('');
  pwdError   = signal('');

  pwdForm = this.fb.group({
    old_password:     ['', Validators.required],
    new_password:     ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', Validators.required],
  });

  get pwf() { return this.pwdForm.controls; }

  ngOnInit(): void {
    this.userApi.getMe().subscribe({
      next: (u) => {
        this.user.set(u as any);
        this.infoForm.patchValue({
          first_name: u.first_name,
          last_name:  u.last_name,
          username:   u.username,
          telephone:  u.telephone,
        });
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  saveInfo(): void {
    if (this.infoForm.invalid || this.infoSaving()) return;
    this.infoSaving.set(true);
    this.infoError.set('');
    this.infoSuccess.set('');

    const raw = this.infoForm.value;
    this.userApi.updateMe({
      first_name: raw.first_name ?? undefined,
      last_name:  raw.last_name  ?? undefined,
      username:   raw.username   ?? undefined,
      telephone:  raw.telephone  ?? undefined,
    } as any).subscribe({
      next: (res) => {
        this.infoSaving.set(false);
        this.infoSuccess.set('Profil mis à jour avec succès.');
        if (res.user) this.user.set(res.user);
      },
      error: (err) => {
        this.infoSaving.set(false);
        this.infoError.set(err?.error?.detail ?? 'Erreur lors de la mise à jour.');
      },
    });
  }

  changePassword(): void {
    if (this.pwdForm.invalid || this.pwdSaving()) return;
    const raw = this.pwdForm.value;
    if (raw.new_password !== raw.confirm_password) {
      this.pwdError.set('Les mots de passe ne correspondent pas.');
      return;
    }
    this.pwdSaving.set(true);
    this.pwdError.set('');
    this.pwdSuccess.set('');

    this.userApi.changePassword({
      old_password: raw.old_password!,
      new_password: raw.new_password!,
    }).subscribe({
      next: () => {
        this.pwdSaving.set(false);
        this.pwdSuccess.set('Mot de passe modifié avec succès.');
        this.pwdForm.reset();
      },
      error: (err) => {
        this.pwdSaving.set(false);
        this.pwdError.set(err?.error?.detail ?? 'Ancien mot de passe incorrect.');
      },
    });
  }
}
