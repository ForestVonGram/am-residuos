import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export interface RouteSummary {
  id: string;
  code: string;
  name: string;
  description: string | null;
  sector: string;
  distance_m: number | null;
}

export interface RouteDetail extends RouteSummary {
  geometry: GeoJSON.LineString;
}

export interface RouteSchedule {
  id: string;
  route_id: string;
  route_code: string;
  route_name: string;
  sector: string;
  service_date: string;
  start_time: string;
  estimated_start_time: string;
  expected_end_time: string;
  duration_minutes: number;
  delay_minutes: number;
  cancelled: boolean;
  delay_reason: string | null;
  truck: { plate: string; name: string } | null;
  personnel: Array<{ name: string; role: string }>;
}

@Injectable({ providedIn: 'root' })
export class CitizenRoutesService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/citizen';

  listRoutes(): Observable<RouteSummary[]> {
    return this.http.get<RouteSummary[]>(`${this.baseUrl}/routes`);
  }

  getRoute(routeId: string): Observable<RouteDetail> {
    return this.http.get<RouteDetail>(`${this.baseUrl}/routes/${routeId}`);
  }

  listSchedules(serviceDate?: string, routeId?: string): Observable<RouteSchedule[]> {
    let params = new HttpParams();
    if (serviceDate) params = params.set('service_date', serviceDate);
    if (routeId) params = params.set('route_id', routeId);
    return this.http.get<RouteSchedule[]>(`${this.baseUrl}/schedules`, { params });
  }
}
