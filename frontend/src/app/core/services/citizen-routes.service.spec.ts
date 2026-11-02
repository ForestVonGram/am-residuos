import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CitizenRoutesService } from './citizen-routes.service';

describe('CitizenRoutesService', () => {
  let service: CitizenRoutesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CitizenRoutesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('solicita ETA con coordenadas y ruta opcional', () => {
    service.getEta(4.53, -75.68, 'route-id').subscribe();

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/v1/citizen/eta' &&
        candidate.params.get('latitude') === '4.53' &&
        candidate.params.get('longitude') === '-75.68' &&
        candidate.params.get('route_id') === 'route-id',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ source: 'scheduled' });
  });

  it('consulta vehículos activos en el endpoint público', () => {
    service.listLiveVehicles().subscribe((vehicles) => expect(vehicles).toEqual([]));

    const request = http.expectOne('/api/v1/citizen/vehicles/live');
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });
});
