import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CitizenRoutesService } from '../../core/services/citizen-routes.service';

vi.mock('maplibre-gl', () => {
  class MockMap {
    once(_event: string, callback: () => void) {
      callback();
    }

    addControl() {}
    addSource() {}
    addLayer() {}
    on() {}
    getSource() {
      return undefined;
    }
    setPaintProperty() {}
    fitBounds() {}
    remove() {}
    getCanvas() {
      return { style: {} };
    }
  }

  class MockMarker {
    addTo() {
      return this;
    }
    setLngLat() {
      return this;
    }
    setRotation() {
      return this;
    }
    remove() {}
  }

  class MockBounds {
    extend() {
      return this;
    }
  }

  return {
    Map: MockMap,
    Marker: MockMarker,
    LngLatBounds: MockBounds,
    NavigationControl: class {},
    setWorkerUrl: vi.fn(),
  };
});

import { RoutesComponent } from './routes.component';

const routeDetail = {
  id: 'route-1',
  code: 'RUTA-1',
  name: 'Ruta Centro',
  description: 'Trazado de demostración',
  sector: 'Centro',
  distance_m: null,
  geometry: {
    type: 'LineString' as const,
    coordinates: [
      [-75.69, 4.53],
      [-75.68, 4.53],
    ],
  },
};

describe('RoutesComponent', () => {
  let fixture: ComponentFixture<RoutesComponent>;
  let service: {
    listRoutes: ReturnType<typeof vi.fn>;
    getRoute: ReturnType<typeof vi.fn>;
    listSchedules: ReturnType<typeof vi.fn>;
    listLiveVehicles: ReturnType<typeof vi.fn>;
    getEta: ReturnType<typeof vi.fn>;
  };
  let intervalCallback: (() => void) | undefined;
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    service = {
      listRoutes: vi.fn(() => of([routeDetail])),
      getRoute: vi.fn(() => of(routeDetail)),
      listSchedules: vi.fn(() => of([])),
      listLiveVehicles: vi.fn(() => of([])),
      getEta: vi.fn(),
    };
    await TestBed.configureTestingModule({
      imports: [RoutesComponent],
      providers: [{ provide: CitizenRoutesService, useValue: service }],
    }).compileComponents();
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ type: 'FeatureCollection', features: [] }),
    } as Response);
    intervalCallback = undefined;
    const nativeSetInterval = window.setInterval.bind(window);
    vi.spyOn(window, 'setInterval').mockImplementation((handler, delay) => {
      if (delay === 5000) {
        intervalCallback = handler as () => void;
        return 123;
      }
      return nativeSetInterval(handler, delay);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renderiza datos mock y etiqueta la simulación', async () => {
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(element.textContent).toContain('Ruta Centro');
    });
    expect(element.textContent).toContain('Simulación GPS');
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('consulta vehículos al cargar y continúa el polling cada cinco segundos', async () => {
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(service.listLiveVehicles).toHaveBeenCalledTimes(1);
    intervalCallback?.();
    await fixture.whenStable();
    expect(service.listLiveVehicles).toHaveBeenCalledTimes(2);
  });

  it('limpia el polling al destruir la página', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    fixture.destroy();

    expect(clearIntervalSpy).toHaveBeenCalledWith(123);
  });
});
