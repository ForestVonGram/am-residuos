import { Routes } from '@angular/router';
import { adminGuard } from './core/guards/admin.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home/home.component').then((module) => module.HomeComponent),
    title: 'Residuos AXM',
  },
  {
    path: 'ayuda',
    loadComponent: () => import('./pages/help/help.component').then((module) => module.HelpComponent),
    title: 'Ayuda | Residuos AXM',
  },
  {
    path: 'contacto',
    loadComponent: () =>
      import('./pages/contact/contact.component').then((module) => module.ContactComponent),
    title: 'Contacto | Residuos AXM',
  },
  {
    path: 'rutas',
    loadComponent: () =>
      import('./pages/routes/routes.component').then((module) => module.RoutesComponent),
    title: 'Rutas | Residuos AXM',
  },
  {
    path: 'admin/login',
    loadComponent: () =>
      import('./pages/admin/login/admin-login.component').then(
        (module) => module.AdminLoginComponent,
      ),
    title: 'Acceso administrativo | Residuos AXM',
  },
  {
    path: 'admin',
    loadComponent: () =>
      import('./pages/admin/dashboard/admin-dashboard.component').then(
        (module) => module.AdminDashboardComponent,
      ),
    canActivate: [adminGuard],
    title: 'Panel administrativo | Residuos AXM',
  },
  { path: '**', redirectTo: '' },
];
