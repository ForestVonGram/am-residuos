import { Routes } from '@angular/router';
import { ContactComponent } from './pages/contact/contact.component';
import { HomeComponent } from './pages/home/home.component';
import { HelpComponent } from './pages/help/help.component';
import { RoutesComponent } from './pages/routes/routes.component';
import { adminGuard } from './core/guards/admin.guard';
import { AdminDashboardComponent } from './pages/admin/dashboard/admin-dashboard.component';
import { AdminLoginComponent } from './pages/admin/login/admin-login.component';

export const routes: Routes = [
  {
    path: '',
    component: HomeComponent,
    title: 'Residuos AXM',
  },
  {
    path: 'ayuda',
    component: HelpComponent,
    title: 'Ayuda | Residuos AXM',
  },
  {
    path: 'contacto',
    component: ContactComponent,
    title: 'Contacto | Residuos AXM',
  },
  {
    path: 'rutas',
    component: RoutesComponent,
    title: 'Rutas | Residuos AXM',
  },
  {
    path: 'admin/login',
    component: AdminLoginComponent,
    title: 'Acceso administrativo | Residuos AXM',
  },
  {
    path: 'admin',
    component: AdminDashboardComponent,
    canActivate: [adminGuard],
    title: 'Panel administrativo | Residuos AXM',
  },
  { path: '**', redirectTo: '' },
];
