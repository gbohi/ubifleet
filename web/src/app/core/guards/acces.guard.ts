// UbiFleet — Garde d'accès aux écrans selon les droits calculés par l'API
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Route protégée par `data: { acces: '<cle>' }` (cf. /auth/me/acces/). */
export const accesGuard: CanActivateFn = route => {
  const auth = inject(AuthService);
  const cle  = route.data?.['acces'] as string | undefined;
  if (!cle || auth.peutAcceder(cle)) {
    return true;
  }
  return inject(Router).createUrlTree(['/dashboard']);
};
