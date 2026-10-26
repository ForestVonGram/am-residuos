import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Observable, finalize } from 'rxjs';
import {
  AdjustmentRecord,
  AdjustmentWrite,
  AdminApiService,
  AdminOverviewData,
  AssignmentRecord,
  AssignmentUpdate,
  AssignmentWrite,
  PersonnelRecord,
  PersonnelWrite,
  ScheduleRecord,
  ScheduleWrite,
  TruckRecord,
  TruckWrite,
} from '../../../core/services/admin-api.service';
import { AdminAuthService } from '../../../core/services/admin-auth.service';

type AdminSection =
  'overview' | 'personnel' | 'trucks' | 'schedules' | 'assignments' | 'adjustments';

type EditableSection = Exclude<AdminSection, 'overview'>;

const EMPTY_DATA: AdminOverviewData = {
  personnel: [],
  trucks: [],
  routes: [],
  schedules: [],
  assignments: [],
  adjustments: [],
};

const emptyPersonnel = (): PersonnelWrite => ({
  first_name: '',
  last_name: '',
  employee_code: null,
  role: 'collector',
});

const emptyTruck = (): TruckWrite => ({
  plate: '',
  name: '',
  brand: null,
  model: null,
  capacity_tons: null,
  status: 'available',
});

const today = (): string => new Date().toISOString().slice(0, 10);

const emptySchedule = (): ScheduleWrite => ({
  route_id: '',
  weekday: 0,
  start_time: '06:00',
  duration_minutes: 120,
  effective_from: today(),
  effective_to: null,
});

const emptyAssignment = (): AssignmentWrite => ({
  route_id: '',
  truck_id: '',
  personnel_ids: [],
  effective_from: today(),
  effective_to: null,
});

const emptyAdjustment = (): AdjustmentWrite => ({
  schedule_id: '',
  service_date: today(),
  delay_minutes: 0,
  cancelled: false,
  reason: null,
});

@Component({
  selector: 'app-admin-dashboard',
  imports: [FormsModule],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.css',
})
export class AdminDashboardComponent implements OnInit {
  protected readonly auth = inject(AdminAuthService);
  protected readonly activeSection = signal<AdminSection>('overview');
  protected readonly data = signal<AdminOverviewData>(EMPTY_DATA);
  protected readonly loading = signal(true);
  protected readonly connectionError = signal(false);
  protected readonly formOpen = signal(false);
  protected readonly editingId = signal<string | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal('');
  protected readonly successMessage = signal('');
  protected readonly sectionTitle = computed(() => {
    const titles: Record<AdminSection, string> = {
      overview: 'Panel administrativo',
      personnel: 'Gestión de empleados',
      trucks: 'Gestión de camiones',
      schedules: 'Gestión de horarios',
      assignments: 'Gestión de asignaciones',
      adjustments: 'Novedades del servicio',
    };
    return titles[this.activeSection()];
  });

  protected personnelForm = emptyPersonnel();
  protected truckForm = emptyTruck();
  protected scheduleForm = emptySchedule();
  protected assignmentForm = emptyAssignment();
  protected adjustmentForm = emptyAdjustment();

  private readonly api = inject(AdminApiService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.loadData();
  }

  protected openSection(section: AdminSection): void {
    this.closeForm();
    this.successMessage.set('');
    this.activeSection.set(section);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  protected beginCreate(): void {
    const section = this.activeSection();
    if (section === 'overview') return;
    this.editingId.set(null);
    this.formError.set('');
    this.successMessage.set('');
    this.resetForm(section);
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
    this.formError.set('');
  }

  protected editPersonnel(person: PersonnelRecord): void {
    this.prepareEdit('personnel', person.id);
    this.personnelForm = {
      first_name: person.first_name,
      last_name: person.last_name,
      employee_code: person.employee_code,
      role: person.role,
    };
  }

  protected editTruck(truck: TruckRecord): void {
    this.prepareEdit('trucks', truck.id);
    this.truckForm = {
      plate: truck.plate,
      name: truck.name,
      brand: truck.brand,
      model: truck.model,
      capacity_tons: truck.capacity_tons,
      status: truck.status,
    };
  }

  protected editSchedule(schedule: ScheduleRecord): void {
    this.prepareEdit('schedules', schedule.id);
    this.scheduleForm = {
      route_id: schedule.route_id,
      weekday: schedule.weekday,
      start_time: schedule.start_time.slice(0, 5),
      duration_minutes: schedule.duration_minutes,
      effective_from: schedule.effective_from,
      effective_to: schedule.effective_to,
    };
  }

  protected editAssignment(assignment: AssignmentRecord): void {
    this.prepareEdit('assignments', assignment.id);
    this.assignmentForm = {
      route_id: assignment.route_id,
      truck_id: assignment.truck.id,
      personnel_ids: assignment.personnel.map((person) => person.id),
      effective_from: assignment.effective_from,
      effective_to: assignment.effective_to,
    };
  }

  protected editAdjustment(adjustment: AdjustmentRecord): void {
    this.prepareEdit('adjustments', adjustment.id);
    this.adjustmentForm = {
      schedule_id: adjustment.schedule_id,
      service_date: adjustment.service_date,
      delay_minutes: adjustment.delay_minutes,
      cancelled: adjustment.cancelled,
      reason: adjustment.reason,
    };
  }

  protected savePersonnel(): void {
    const payload: PersonnelWrite = {
      ...this.personnelForm,
      first_name: this.personnelForm.first_name.trim(),
      last_name: this.personnelForm.last_name.trim(),
      employee_code: this.cleanOptional(this.personnelForm.employee_code),
    };
    const id = this.editingId();
    this.perform(
      id ? this.api.updatePersonnel(id, payload) : this.api.createPersonnel(payload),
      id ? 'Empleado actualizado.' : 'Empleado creado.',
    );
  }

  protected saveTruck(): void {
    const payload: TruckWrite = {
      ...this.truckForm,
      plate: this.truckForm.plate.trim().toUpperCase(),
      name: this.truckForm.name.trim(),
      brand: this.cleanOptional(this.truckForm.brand),
      model: this.cleanOptional(this.truckForm.model),
      capacity_tons: this.truckForm.capacity_tons || null,
    };
    const id = this.editingId();
    this.perform(
      id ? this.api.updateTruck(id, payload) : this.api.createTruck(payload),
      id ? 'Camión actualizado.' : 'Camión creado.',
    );
  }

  protected saveSchedule(): void {
    const payload: ScheduleWrite = {
      ...this.scheduleForm,
      effective_to: this.cleanOptional(this.scheduleForm.effective_to),
    };
    const id = this.editingId();
    if (id) {
      const { route_id: _, ...update } = payload;
      this.perform(this.api.updateSchedule(id, update), 'Horario actualizado.');
      return;
    }
    this.perform(this.api.createSchedule(payload), 'Horario creado.');
  }

  protected saveAssignment(): void {
    const payload: AssignmentWrite = {
      ...this.assignmentForm,
      effective_to: this.cleanOptional(this.assignmentForm.effective_to),
    };
    const id = this.editingId();
    if (id) {
      const { route_id: _, ...update } = payload;
      this.perform(
        this.api.updateAssignment(id, update as AssignmentUpdate),
        'Asignación actualizada.',
      );
      return;
    }
    this.perform(this.api.createAssignment(payload), 'Asignación creada.');
  }

  protected saveAdjustment(): void {
    const payload: AdjustmentWrite = {
      ...this.adjustmentForm,
      delay_minutes: this.adjustmentForm.cancelled ? 0 : this.adjustmentForm.delay_minutes,
      reason: this.cleanOptional(this.adjustmentForm.reason),
    };
    this.perform(this.api.saveAdjustment(payload), 'Novedad guardada.');
  }

  protected deactivatePersonnel(person: PersonnelRecord): void {
    if (!confirm(`¿Desactivar a ${person.first_name} ${person.last_name}?`)) return;
    this.perform(this.api.deactivatePersonnel(person.id), 'Empleado desactivado.');
  }

  protected deactivateTruck(truck: TruckRecord): void {
    if (!confirm(`¿Desactivar el camión ${truck.plate}?`)) return;
    this.perform(this.api.deactivateTruck(truck.id), 'Camión desactivado.');
  }

  protected deactivateSchedule(schedule: ScheduleRecord): void {
    if (!confirm(`¿Desactivar el horario de ${this.routeName(schedule.route_id)}?`)) return;
    this.perform(this.api.deactivateSchedule(schedule.id), 'Horario desactivado.');
  }

  protected deactivateAssignment(assignment: AssignmentRecord): void {
    if (!confirm(`¿Desactivar la asignación de ${this.routeName(assignment.route_id)}?`)) return;
    this.perform(this.api.deactivateAssignment(assignment.id), 'Asignación desactivada.');
  }

  protected deleteAdjustment(adjustment: AdjustmentRecord): void {
    if (!confirm('¿Eliminar esta novedad del servicio?')) return;
    this.perform(
      this.api.deleteAdjustment(adjustment.schedule_id, adjustment.service_date),
      'Novedad eliminada.',
    );
  }

  protected togglePersonnel(personnelId: string, checked: boolean): void {
    const selected = new Set(this.assignmentForm.personnel_ids);
    checked ? selected.add(personnelId) : selected.delete(personnelId);
    this.assignmentForm.personnel_ids = [...selected];
  }

  protected isPersonnelSelected(personnelId: string): boolean {
    return this.assignmentForm.personnel_ids.includes(personnelId);
  }

  protected loadData(): void {
    this.loading.set(true);
    this.connectionError.set(false);
    this.api
      .loadOverview()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.data.set(data);
          this.loading.set(false);
        },
        error: () => {
          this.data.set(EMPTY_DATA);
          this.connectionError.set(true);
          this.loading.set(false);
        },
      });
  }

  protected logout(): void {
    this.auth.logout();
    void this.router.navigateByUrl('/admin/login');
  }

  protected roleLabel(role: string): string {
    return { driver: 'Conductor', collector: 'Recolector', supervisor: 'Supervisor' }[role] ?? role;
  }

  protected truckStatusLabel(status: string): string {
    return (
      {
        available: 'Disponible',
        maintenance: 'Mantenimiento',
        out_of_service: 'Fuera de servicio',
      }[status] ?? status
    );
  }

  protected weekdayLabel(day: number): string {
    return ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][day] ?? '—';
  }

  protected routeName(routeId: string): string {
    return this.data().routes.find((route) => route.id === routeId)?.name ?? routeId.slice(0, 8);
  }

  protected scheduleName(scheduleId: string): string {
    const schedule = this.data().schedules.find((item) => item.id === scheduleId);
    return schedule
      ? `${this.routeName(schedule.route_id)} · ${this.weekdayLabel(schedule.weekday)} ${schedule.start_time.slice(0, 5)}`
      : scheduleId.slice(0, 8);
  }

  protected formatDate(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      timeZone: 'America/Bogota',
    }).format(new Date(`${value}T12:00:00`));
  }

  private prepareEdit(section: EditableSection, id: string): void {
    this.activeSection.set(section);
    this.editingId.set(id);
    this.formError.set('');
    this.successMessage.set('');
    this.formOpen.set(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  private resetForm(section: EditableSection): void {
    if (section === 'personnel') this.personnelForm = emptyPersonnel();
    if (section === 'trucks') this.truckForm = emptyTruck();
    if (section === 'schedules') this.scheduleForm = emptySchedule();
    if (section === 'assignments') this.assignmentForm = emptyAssignment();
    if (section === 'adjustments') this.adjustmentForm = emptyAdjustment();
  }

  private perform(request: Observable<unknown>, message: string): void {
    this.saving.set(true);
    this.formError.set('');
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.closeForm();
          this.successMessage.set(message);
          this.loadData();
        },
        error: (error: HttpErrorResponse) => {
          this.formError.set(this.errorMessage(error));
        },
      });
  }

  private errorMessage(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg ?? 'Dato inválido').join('. ');
    }
    return 'No fue posible guardar los cambios. Revisa los datos e intenta de nuevo.';
  }

  private cleanOptional(value: string | null): string | null {
    const cleaned = value?.trim();
    return cleaned ? cleaned : null;
  }
}
