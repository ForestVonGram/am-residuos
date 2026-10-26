import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin } from 'rxjs';
import { RouteSummary } from './citizen-routes.service';
import { AdminAuthService } from './admin-auth.service';

export interface PersonnelRecord {
  id: string;
  first_name: string;
  last_name: string;
  employee_code: string | null;
  role: 'driver' | 'collector' | 'supervisor';
  active: boolean;
}

export interface TruckRecord {
  id: string;
  plate: string;
  name: string;
  brand: string | null;
  model: string | null;
  capacity_tons: number | null;
  status: 'available' | 'maintenance' | 'out_of_service';
  active: boolean;
}

export interface ScheduleRecord {
  id: string;
  route_id: string;
  weekday: number;
  start_time: string;
  duration_minutes: number;
  effective_from: string;
  effective_to: string | null;
  active: boolean;
}

export interface AssignmentRecord {
  id: string;
  route_id: string;
  truck: TruckRecord;
  personnel: PersonnelRecord[];
  effective_from: string;
  effective_to: string | null;
  active: boolean;
}

export interface AdjustmentRecord {
  id: string;
  schedule_id: string;
  service_date: string;
  delay_minutes: number;
  cancelled: boolean;
  reason: string | null;
}

export interface AdminOverviewData {
  personnel: PersonnelRecord[];
  trucks: TruckRecord[];
  routes: RouteSummary[];
  schedules: ScheduleRecord[];
  assignments: AssignmentRecord[];
  adjustments: AdjustmentRecord[];
}

export type PersonnelWrite = Omit<PersonnelRecord, 'id' | 'active'>;
export type PersonnelUpdate = Partial<PersonnelWrite> & { active?: boolean };
export type TruckWrite = Omit<TruckRecord, 'id' | 'active'>;
export type TruckUpdate = Partial<TruckWrite> & { active?: boolean };
export type ScheduleWrite = Omit<ScheduleRecord, 'id' | 'active'>;
export type ScheduleUpdate = Partial<Omit<ScheduleWrite, 'route_id'>> & {
  active?: boolean;
};

export interface AssignmentWrite {
  route_id: string;
  truck_id: string;
  personnel_ids: string[];
  effective_from: string;
  effective_to: string | null;
}

export type AssignmentUpdate = Omit<AssignmentWrite, 'route_id'> & {
  active?: boolean;
};

export type AdjustmentWrite = Omit<AdjustmentRecord, 'id'>;

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AdminAuthService);
  private readonly adminUrl = '/api/v1/admin';

  private get options() {
    return {
      headers: new HttpHeaders({ 'X-Admin-Key': this.auth.adminApiKey }),
    };
  }

  loadOverview(): Observable<AdminOverviewData> {
    return forkJoin({
      personnel: this.http.get<PersonnelRecord[]>(`${this.adminUrl}/personnel`, this.options),
      trucks: this.http.get<TruckRecord[]>(`${this.adminUrl}/trucks`, this.options),
      routes: this.http.get<RouteSummary[]>('/api/v1/citizen/routes'),
      schedules: this.http.get<ScheduleRecord[]>(`${this.adminUrl}/schedules`, this.options),
      assignments: this.http.get<AssignmentRecord[]>(`${this.adminUrl}/assignments`, this.options),
      adjustments: this.http.get<AdjustmentRecord[]>(
        `${this.adminUrl}/service-adjustments`,
        this.options,
      ),
    });
  }

  createPersonnel(data: PersonnelWrite): Observable<PersonnelRecord> {
    return this.http.post<PersonnelRecord>(`${this.adminUrl}/personnel`, data, this.options);
  }

  updatePersonnel(id: string, data: PersonnelUpdate): Observable<PersonnelRecord> {
    return this.http.patch<PersonnelRecord>(`${this.adminUrl}/personnel/${id}`, data, this.options);
  }

  deactivatePersonnel(id: string): Observable<void> {
    return this.http.delete<void>(`${this.adminUrl}/personnel/${id}`, this.options);
  }

  createTruck(data: TruckWrite): Observable<TruckRecord> {
    return this.http.post<TruckRecord>(`${this.adminUrl}/trucks`, data, this.options);
  }

  updateTruck(id: string, data: TruckUpdate): Observable<TruckRecord> {
    return this.http.patch<TruckRecord>(`${this.adminUrl}/trucks/${id}`, data, this.options);
  }

  deactivateTruck(id: string): Observable<void> {
    return this.http.delete<void>(`${this.adminUrl}/trucks/${id}`, this.options);
  }

  createSchedule(data: ScheduleWrite): Observable<ScheduleRecord> {
    return this.http.post<ScheduleRecord>(`${this.adminUrl}/schedules`, data, this.options);
  }

  updateSchedule(id: string, data: ScheduleUpdate): Observable<ScheduleRecord> {
    return this.http.patch<ScheduleRecord>(`${this.adminUrl}/schedules/${id}`, data, this.options);
  }

  deactivateSchedule(id: string): Observable<void> {
    return this.http.delete<void>(`${this.adminUrl}/schedules/${id}`, this.options);
  }

  createAssignment(data: AssignmentWrite): Observable<AssignmentRecord> {
    return this.http.post<AssignmentRecord>(`${this.adminUrl}/assignments`, data, this.options);
  }

  updateAssignment(id: string, data: AssignmentUpdate): Observable<AssignmentRecord> {
    return this.http.patch<AssignmentRecord>(
      `${this.adminUrl}/assignments/${id}`,
      data,
      this.options,
    );
  }

  deactivateAssignment(id: string): Observable<void> {
    return this.http.delete<void>(`${this.adminUrl}/assignments/${id}`, this.options);
  }

  saveAdjustment(data: AdjustmentWrite): Observable<AdjustmentRecord> {
    return this.http.put<AdjustmentRecord>(
      `${this.adminUrl}/service-adjustments`,
      data,
      this.options,
    );
  }

  deleteAdjustment(scheduleId: string, serviceDate: string): Observable<void> {
    return this.http.delete<void>(
      `${this.adminUrl}/service-adjustments/${scheduleId}/${serviceDate}`,
      this.options,
    );
  }
}
