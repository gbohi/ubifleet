// UbiFleet — JWT HTTP Interceptor
import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth  = inject(AuthService);
  const token = auth.getAccessToken();

  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      // Login, refresh et logout ne déclenchent pas de rafraîchissement ;
      // /auth/me/ et les autres routes du compte, si.
      const routeAuth = /\/auth\/(login|token\/refresh|logout)\//.test(req.url);
      if (err.status === 401 && !routeAuth && auth.isLoggedIn()) {
        return auth.refreshToken().pipe(
          switchMap(access => next(
            req.clone({ setHeaders: { Authorization: `Bearer ${access}` } })
          )),
          catchError(refreshErr => {
            auth.logout();
            return throwError(() => refreshErr);
          })
        );
      }
      return throwError(() => err);
    })
  );
};
