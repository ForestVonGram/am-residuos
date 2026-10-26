import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AdminAuthService } from '../../../core/services/admin-auth.service';

@Component({
  selector: 'app-admin-login',
  imports: [FormsModule],
  templateUrl: './admin-login.component.html',
  styleUrl: './admin-login.component.css',
})
export class AdminLoginComponent {
  protected email = '';
  protected password = '';
  protected readonly errorMessage = signal('');
  protected readonly auth = inject(AdminAuthService);

  private readonly router = inject(Router);

  protected fillDemoCredentials(): void {
    this.email = this.auth.demoEmail;
    this.password = this.auth.demoPassword;
    this.errorMessage.set('');
  }

  protected submit(): void {
    if (!this.auth.login(this.email, this.password)) {
      this.errorMessage.set('El usuario o la contraseña no son correctos.');
      return;
    }
    void this.router.navigateByUrl('/admin');
  }
}
