import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, map, of, tap, throwError } from 'rxjs';

export interface AdminUser {
  name: string;
  email: string;
}

interface AdminSessionResponse {
  username: string;
}

@Injectable({ providedIn: 'root' })
export class AdminAuthService {
  private readonly http = inject(HttpClient);
  private readonly authUrl = '/api/v1/admin/auth';
  private readonly userState = signal<AdminUser | null>(null);

  readonly user = this.userState.asReadonly();
  readonly isAuthenticated = computed(() => this.userState() !== null);

  login(username: string, password: string): Observable<AdminUser> {
    return this.http
      .post<AdminSessionResponse>(`${this.authUrl}/login`, { username, password })
      .pipe(map((session) => this.setUser(session.username)));
  }

  restoreSession(): Observable<AdminUser | null> {
    if (this.userState()) return of(this.userState());
    return this.http.get<AdminSessionResponse>(`${this.authUrl}/session`).pipe(
      map((session) => this.setUser(session.username)),
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401) {
          this.userState.set(null);
          return of(null);
        }
        return throwError(() => error);
      }),
    );
  }

  logout(): Observable<void> {
    return this.http.post<void>(`${this.authUrl}/logout`, {}).pipe(
      tap(() => this.userState.set(null)),
    );
  }

  private setUser(username: string): AdminUser {
    const user = { name: 'ADMIN', email: username };
    this.userState.set(user);
    return user;
  }
}
