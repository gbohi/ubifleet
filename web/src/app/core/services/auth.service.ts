// UbiFleet — Auth Service
import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { environment } from '@env/environment';
import { LoginRequest, LoginResponse, User } from '../models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http   = inject(HttpClient);
  private router = inject(Router);

  private readonly ACCESS_KEY  = 'ubi_access';
  private readonly REFRESH_KEY = 'ubi_refresh';
  private readonly USER_KEY    = 'ubi_user';

  // Signals
  currentUser = signal<User | null>(this.loadUser());
  isLoggedIn  = computed(() => !!this.currentUser());
  isAdmin     = computed(() =>
    ['super_admin', 'dg', 'responsable_flotte'].includes(this.currentUser()?.role ?? '')
  );

  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(
      `${environment.apiUrl}/auth/login/`, credentials
    ).pipe(
      tap(res => {
        localStorage.setItem(this.ACCESS_KEY,  res.access);
        localStorage.setItem(this.REFRESH_KEY, res.refresh);
        localStorage.setItem(this.USER_KEY,    JSON.stringify(res.user));
        this.currentUser.set(res.user);
      }),
      catchError(err => throwError(() => err))
    );
  }

  logout(): void {
    const refresh = localStorage.getItem(this.REFRESH_KEY);
    if (refresh) {
      this.http.post(`${environment.apiUrl}/auth/logout/`, { refresh })
        .subscribe({ error: () => {} });
    }
    localStorage.removeItem(this.ACCESS_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.currentUser.set(null);
    this.router.navigate(['/auth/login']);
  }

  refreshToken(): Observable<{ access: string }> {
    const refresh = localStorage.getItem(this.REFRESH_KEY);
    return this.http.post<{ access: string }>(
      `${environment.apiUrl}/auth/token/refresh/`, { refresh }
    ).pipe(
      tap(res => localStorage.setItem(this.ACCESS_KEY, res.access)),
      catchError(err => {
        this.logout();
        return throwError(() => err);
      })
    );
  }

  getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_KEY);
  }

  private loadUser(): User | null {
    try {
      const u = localStorage.getItem(this.USER_KEY);
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  }
}
