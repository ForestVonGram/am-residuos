import { HttpErrorResponse } from '@angular/common/http';
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
  protected username = '';
  protected password = '';
  protected readonly errorMessage = signal('');
  protected readonly auth = inject(AdminAuthService);

  private readonly router = inject(Router);

  protected submit(): void {
    this.errorMessage.set('');
    this.auth.login(this.username, this.password).subscribe({
      next: () => void this.router.navigateByUrl('/admin'),
      error: (error: HttpErrorResponse) => {
        this.errorMessage.set(
          error.status === 401
            ? 'El usuario o la contraseña no son correctos.'
            : error.status === 503
              ? 'La autenticación administrativa no está configurada en el servidor.'
              : 'No fue posible iniciar sesión. Inténtalo de nuevo.',
        );
      },
    });
  }
}
