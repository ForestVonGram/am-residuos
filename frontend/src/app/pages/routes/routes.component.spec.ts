import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CitizenRoutesService } from '../../core/services/citizen-routes.service';

const mapMocks = vi.hoisted(() => ({
  fitBounds: vi.fn(),
  flyTo: vi.fn(),
  mapClick: undefined as
    | ((event: { lngLat: { lng: number; lat: number } }) => void)
    | undefined,
  markerOptions: [] as Array<{
    anchor?: string;
    offset?: [number, number];
  }>,
  markerLocations: [] as Array<[number, number]>,
  markerLabels: [] as string[],
  citizenLocationData: [] as unknown[],
}));

vi.mock('maplibre-gl', () => {
  class MockMarker {
    private readonly element: HTMLElement;

    constructor(options: {
      element: HTMLElement;
      anchor?: string;
      offset?: [number, number];
    }) {
      this.element = options.element;
      mapMocks.markerOptions.push({
        anchor: options.anchor,
        offset: options.offset,
      });
      mapMocks.markerLabels.push(this.element.getAttribute('aria-label') ?? '');
    }

    addTo() {
      return this;
    }

    setLngLat(coordinates: [number, number]) {
      mapMocks.markerLocations.push(coordinates);
      return this;
    }

    setRotation() {
      return this;
    }

    getElement() {
      return this.element;
    }

    remove() {}
  }

  class MockMap {
    once(_event: string, callback: () => void) {
      callback();
    }

    addControl() {}
    addSource(id: string, source: { data?: unknown }) {
      if (id === 'citizen-location') {
        mapMocks.citizenLocationData.push(source.data);
      }
    }
    addLayer() {}
    on(
      event: string,
      handler: (event: { lngLat: { lng: number; lat: number } }) => void,
    ) {
      if (event === 'click') {
        mapMocks.mapClick = handler;
      }
    }
    getSource(id: string) {
      return id === 'citizen-location'
        ? {
            setData(data: unknown) {
              mapMocks.citizenLocationData.push(data);
            },
          }
        : undefined;
    }
    setPaintProperty() {}
    fitBounds(...args: unknown[]) {
      mapMocks.fitBounds(...args);
    }
    flyTo(...args: unknown[]) {
      mapMocks.flyTo(...args);
    }
    remove() {}
    getCanvas() {
      return { style: {} };
    }
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
    mapMocks.fitBounds.mockClear();
    mapMocks.flyTo.mockClear();
    mapMocks.markerOptions.length = 0;
    mapMocks.markerLocations.length = 0;
    mapMocks.markerLabels.length = 0;
    mapMocks.citizenLocationData.length = 0;
    mapMocks.mapClick = undefined;
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

  it('muestra el camión y actualiza su posición con cada respuesta GPS', async () => {
    const firstVehicle = {
      truck_plate: 'AXM-001',
      truck_name: 'Camión demo',
      latitude: 4.53,
      longitude: -75.69,
      speed_kmh: 20,
      heading: 90,
      recorded_at: '2026-11-02T22:00:00Z',
      stale: false,
      route_id: 'route-1',
      simulated: true,
    };
    service.listLiveVehicles = vi
      .fn()
      .mockReturnValueOnce(of([firstVehicle]))
      .mockReturnValueOnce(
        of([{ ...firstVehicle, latitude: 4.54, longitude: -75.68 }]),
      );
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mapMocks.markerLabels).toContain('Camión Camión demo, simulación');
    expect(mapMocks.markerLocations).toContainEqual([-75.69, 4.53]);

    intervalCallback?.();
    await fixture.whenStable();

    expect(mapMocks.markerLocations).toContainEqual([-75.68, 4.54]);
  });

  it('no muestra camiones con una posición GPS desactualizada', async () => {
    service.listLiveVehicles = vi.fn(() =>
      of([
        {
          truck_plate: 'AXM-001',
          truck_name: 'Camión demo',
          latitude: 4.53,
          longitude: -75.69,
          speed_kmh: 20,
          heading: 90,
          recorded_at: '2026-11-02T22:00:00Z',
          stale: true,
          route_id: 'route-1',
          simulated: true,
        },
      ]),
    );
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mapMocks.markerLabels).not.toContain('Camión Camión demo, simulación');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'No hay camiones con ubicación GPS reciente en este momento.',
    );
  });

  it('limpia el polling al destruir la página', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    fixture.destroy();

    expect(clearIntervalSpy).toHaveBeenCalledWith(123);
  });

  it('vuelve a encuadrar la ruta incluso si ya estaba seleccionada', async () => {
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    const element = fixture.nativeElement as HTMLElement;
    await vi.waitFor(() =>
      expect(element.querySelector('.route-selector button')).not.toBeNull(),
    );
    const callsBefore = mapMocks.fitBounds.mock.calls.length;

    const routeButton = element.querySelector<HTMLButtonElement>('.route-selector button');
    routeButton?.click();

    expect(mapMocks.fitBounds.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it('muestra en la coordenada exacta el punto elegido en el mapa', async () => {
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    mapMocks.mapClick?.({ lngLat: { lng: -75.68, lat: 4.53 } });
    fixture.detectChanges();

    const consultButton = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button'),
    ).find((button) => button.textContent?.includes('Consultar punto del mapa'));
    consultButton?.click();

    expect(service.getEta).toHaveBeenCalledWith(4.53, -75.68);
    expect(mapMocks.citizenLocationData.at(-1)).toEqual(
      expect.objectContaining({
        features: [
          expect.objectContaining({
            geometry: { type: 'Point', coordinates: [-75.68, 4.53] },
          }),
        ],
      }),
    );
  });

  it('centra el mapa y actualiza la capa con la ubicación compartida', async () => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: (success: PositionCallback) =>
          success({
            coords: { latitude: 4.54, longitude: -75.67 },
          } as GeolocationPosition),
      },
    });
    fixture = TestBed.createComponent(RoutesComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    const shareButton = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button'),
    ).find((button) => button.textContent?.includes('Compartir ubicación'));
    shareButton?.click();

    expect(mapMocks.flyTo).toHaveBeenCalledWith({
      center: [-75.67, 4.54],
      zoom: 16,
      duration: 700,
    });
    expect(mapMocks.citizenLocationData.at(-1)).toEqual(
      expect.objectContaining({
        features: [
          expect.objectContaining({
            geometry: { type: 'Point', coordinates: [-75.67, 4.54] },
          }),
        ],
      }),
    );
  });
});
