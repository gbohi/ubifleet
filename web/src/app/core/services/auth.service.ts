// UbiFleet — Auth Service
import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError, map, shareReplay, finalize } from 'rxjs';
import { environment } from '@env/environment';
import { LoginRequest, LoginResponse, User } from '../models';

/** Écrans accessibles à l'utilisateur, calculés par l'API (/auth/me/acces/). */
export type AccesEcrans = Record<string, boolean>;

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http   = inject(HttpClient);
  private router = inject(Router);

  private readonly ACCESS_KEY  = 'ubi_access';
  private readonly REFRESH_KEY = 'ubi_refresh';
  private readonly USER_KEY    = 'ubi_user';
  private readonly ACCES_KEY   = 'ubi_acces';

  // Rafraîchissement en cours, partagé entre toutes les requêtes en 401 :
  // le backend fait tourner le refresh token (ROTATE + BLACKLIST), un second
  // appel avec l'ancien jeton échouerait et déconnecterait l'utilisateur.
  private refreshEnCours$: Observable<string> | null = null;

  // Signals
  currentUser = signal<User | null>(this.loadJson<User>(this.USER_KEY));
  acces       = signal<AccesEcrans | null>(this.loadJson<AccesEcrans>(this.ACCES_KEY));
  isLoggedIn  = computed(() => !!this.currentUser());
  isAdmin     = computed(() =>
    ['super_admin', 'dg', 'responsable_flotte'].includes(this.currentUser()?.role ?? '')
  );

  /** Droits pas encore chargés → on ne masque rien (l'API reste le garde-fou). */
  peutAcceder(cle: string): boolean {
    const acces = this.acces();
    return !acces || acces[cle] !== false;
  }

  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(
      `${environment.apiUrl}/auth/login/`, credentials
    ).pipe(
      tap(res => {
        localStorage.setItem(this.ACCESS_KEY,  res.access);
        localStorage.setItem(this.REFRESH_KEY, res.refresh);
        localStorage.setItem(this.USER_KEY,    JSON.stringify(res.user));
        this.currentUser.set(res.user);
        this.chargerAcces();
      }),
      catchError(err => throwError(() => err))
    );
  }

  /** Recharge le profil et les droits (rôle ou agence modifiés entre-temps). */
  rafraichirSession(): void {
    this.http.get<User>(`${environment.apiUrl}/auth/me/`).subscribe({
      next: user => {
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        this.currentUser.set(user);
      },
      error: () => {},
    });
    this.chargerAcces();
  }

  private chargerAcces(): void {
    this.http.get<AccesEcrans>(`${environment.apiUrl}/auth/me/acces/`).subscribe({
      next: acces => {
        localStorage.setItem(this.ACCES_KEY, JSON.stringify(acces));
        this.acces.set(acces);
      },
      error: () => {},
    });
  }

  logout(): void {
    const refresh = localStorage.getItem(this.REFRESH_KEY);
    if (refresh) {
      this.http.post(`${environment.apiUrl}/auth/logout/`, { refresh })
        .subscribe({ error: () => {} });
    }
    this.clearSession();
    this.router.navigate(['/auth/login']);
  }

  /**
   * Obtient un nouveau jeton d'accès. Les appels simultanés partagent la même
   * requête ; le nouveau refresh token renvoyé par l'API est conservé.
   */
  refreshToken(): Observable<string> {
    if (this.refreshEnCours$) {
      return this.refreshEnCours$;
    }
    const refresh = localStorage.getItem(this.REFRESH_KEY);
    if (!refresh) {
      return throwError(() => new Error('Aucun refresh token'));
    }
    this.refreshEnCours$ = this.http.post<{ access: string; refresh?: string }>(
      `${environment.apiUrl}/auth/token/refresh/`, { refresh }
    ).pipe(
      tap(res => {
        localStorage.setItem(this.ACCESS_KEY, res.access);
        if (res.refresh) {
          localStorage.setItem(this.REFRESH_KEY, res.refresh);
        }
      }),
      map(res => res.access),
      finalize(() => this.refreshEnCours$ = null),
      shareReplay(1),
    );
    return this.refreshEnCours$;
  }

  getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_KEY);
  }

  private clearSession(): void {
    localStorage.removeItem(this.ACCESS_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
    localStorage.removeItem(this.USER_KEY);
    localStorage.removeItem(this.ACCES_KEY);
    this.currentUser.set(null);
    this.acces.set(null);
  }

  private loadJson<T>(key: string): T | null {
    try {
      const v = localStorage.getItem(key);
      return v ? JSON.parse(v) : null;
    } catch {
      return null;
    }
  }
}
