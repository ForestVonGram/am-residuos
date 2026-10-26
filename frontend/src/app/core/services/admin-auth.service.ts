import { Injectable, computed, signal } from '@angular/core';

export interface AdminUser {
  name: string;
  email: string;
}

@Injectable({ providedIn: 'root' })
export class AdminAuthService {
  readonly demoEmail = 'admin@axmresiduos.com';
  readonly demoPassword = 'AdminAXM2026!';

  private readonly sessionKey = 'axm-demo-admin-session';
  private readonly userState = signal<AdminUser | null>(this.restoreSession());

  readonly user = this.userState.asReadonly();
  readonly isAuthenticated = computed(() => this.userState() !== null);

  get adminApiKey(): string {
    return 'change-me-local-only';
  }

  login(email: string, password: string): boolean {
    const isValid =
      email.trim().toLowerCase() === this.demoEmail &&
      password === this.demoPassword;

    if (!isValid) return false;

    const user: AdminUser = { name: 'ADMIN', email: this.demoEmail };
    sessionStorage.setItem(this.sessionKey, JSON.stringify(user));
    this.userState.set(user);
    return true;
  }

  logout(): void {
    sessionStorage.removeItem(this.sessionKey);
    this.userState.set(null);
  }

  private restoreSession(): AdminUser | null {
    const value = sessionStorage.getItem(this.sessionKey);
    if (!value) return null;
    try {
      return JSON.parse(value) as AdminUser;
    } catch {
      sessionStorage.removeItem(this.sessionKey);
      return null;
    }
  }
}
