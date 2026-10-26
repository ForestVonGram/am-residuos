import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';
import type {
  Feature,
  FeatureCollection,
  LineString,
  Point,
} from 'geojson';
import {
  GeoJSONSource,
  LngLatBounds,
  Map,
  NavigationControl,
  setWorkerUrl,
  StyleSpecification,
} from 'maplibre-gl';
import { firstValueFrom } from 'rxjs';
import {
  CitizenRoutesService,
  RouteSchedule,
} from '../../core/services/citizen-routes.service';

interface GeoJsonRouteProperties {
  id: string;
  code: string;
  name: string;
  sector: string;
}

interface RouteView extends GeoJsonRouteProperties {
  description: string | null;
  geometry: LineString;
  schedule: RouteSchedule | null;
}

type RoutesCollection = FeatureCollection<LineString, GeoJsonRouteProperties>;

@Component({
  selector: 'app-routes',
  templateUrl: './routes.component.html',
  styleUrl: './routes.component.css',
})
export class RoutesComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('mapContainer') private mapContainer?: ElementRef<HTMLElement>;

  protected readonly routes = signal<readonly RouteView[]>([]);
  protected readonly selectedRouteId = signal('');
  protected readonly loading = signal(true);
  protected readonly mapReady = signal(false);
  protected readonly usingLocalData = signal(true);
  protected readonly selectedRoute = computed(
    () =>
      this.routes().find((route) => route.id === this.selectedRouteId()) ??
      null,
  );

  private readonly routeService = inject(CitizenRoutesService);
  private readonly fallbackUrl = '/map-data/rutas.geojson';
  private map?: Map;

  ngOnInit(): void {
    void this.loadRoutes();
  }

  ngAfterViewInit(): void {
    this.initializeMap();
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  protected selectRoute(routeId: string): void {
    if (this.selectedRouteId() === routeId) {
      return;
    }

    this.selectedRouteId.set(routeId);
    this.updateSelectedRouteOnMap(true);
  }

  protected formatDate(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      timeZone: 'America/Bogota',
    }).format(new Date(`${value}T12:00:00`));
  }

  protected formatTime(value: string): string {
    const [hour = '00', minute = '00'] = value.split(':');
    const parsedHour = Number(hour);
    const suffix = parsedHour >= 12 ? 'p. m.' : 'a. m.';
    const displayHour = parsedHour % 12 || 12;
    return `${displayHour}:${minute} ${suffix}`;
  }

  protected roleLabel(role: string): string {
    return (
      { driver: 'Conductor', collector: 'Recolector', supervisor: 'Supervisor' }[
        role
      ] ?? role
    );
  }

  private async loadUpcomingSchedules(): Promise<RouteSchedule[]> {
    const formatter = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: 'America/Bogota',
    });
    const today = new Date();
    const dates = Array.from({ length: 8 }, (_, offset) => {
      const date = new Date(today);
      date.setDate(today.getDate() + offset);
      return formatter.format(date);
    });
    const groups = await Promise.all(
      dates.map((date) =>
        firstValueFrom(this.routeService.listSchedules(date)),
      ),
    );
    return groups
      .flat()
      .sort((a, b) =>
        `${a.service_date}T${a.estimated_start_time}`.localeCompare(
          `${b.service_date}T${b.estimated_start_time}`,
        ),
      );
  }

  private async loadRoutes(): Promise<void> {
    const fallback = await this.loadFallbackRoutes();
    this.applyRoutes(fallback, [], true);

    try {
      const summaries = await firstValueFrom(this.routeService.listRoutes());
      if (!summaries.length) {
        return;
      }

      const [details, schedules] = await Promise.all([
        Promise.all(
          summaries.map((route) =>
            firstValueFrom(this.routeService.getRoute(route.id)),
          ),
        ),
        this.loadUpcomingSchedules(),
      ]);

      const collection: RoutesCollection = {
        type: 'FeatureCollection',
        features: details.map((route) => ({
          type: 'Feature',
          properties: {
            id: route.id,
            code: route.code,
            name: route.name,
            sector: route.sector,
          },
          geometry: route.geometry,
        })),
      };

      this.applyRoutes(collection, schedules, false, details);
    } catch {
      this.usingLocalData.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  private async loadFallbackRoutes(): Promise<RoutesCollection> {
    const response = await fetch(this.fallbackUrl);
    if (!response.ok) {
      throw new Error('No fue posible cargar el archivo local de rutas.');
    }
    return (await response.json()) as RoutesCollection;
  }

  private applyRoutes(
    collection: RoutesCollection,
    schedules: RouteSchedule[],
    local: boolean,
    details?: Array<{ id: string; description: string | null }>,
  ): void {
    const routes = collection.features.map((feature) => {
      const properties = feature.properties;
      return {
        ...properties,
        description:
          details?.find((detail) => detail.id === properties.id)?.description ??
          null,
        geometry: feature.geometry,
        schedule:
          schedules.find(
            (schedule) =>
              schedule.route_id === properties.id && !schedule.cancelled,
          ) ??
          schedules.find((schedule) => schedule.route_id === properties.id) ??
          null,
      };
    });

    this.routes.set(routes);
    this.usingLocalData.set(local);
    if (!routes.some((route) => route.id === this.selectedRouteId())) {
      this.selectedRouteId.set(routes[0]?.id ?? '');
    }
    this.renderRoutes(collection);
  }

  private initializeMap(): void {
    if (!this.mapContainer) {
      return;
    }

    setWorkerUrl('/maplibre-gl-worker.mjs');

    const style: StyleSpecification = {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
    };

    this.map = new Map({
      container: this.mapContainer.nativeElement,
      style,
      center: [-75.6811, 4.5339],
      zoom: 12,
    });
    this.map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    this.map.once('style.load', () => {
      this.mapReady.set(true);
      this.renderRoutes(this.toFeatureCollection(this.routes()));
    });
  }

  private renderRoutes(collection: RoutesCollection): void {
    if (!this.map || !this.mapReady() || !collection.features.length) {
      return;
    }

    const source = this.map.getSource('collection-routes') as
      | GeoJSONSource
      | undefined;
    if (source) {
      source.setData(collection);
    } else {
      this.map.addSource('collection-routes', {
        type: 'geojson',
        data: collection,
      });
      this.map.addLayer({
        id: 'route-outline',
        type: 'line',
        source: 'collection-routes',
        paint: {
          'line-color': '#ffffff',
          'line-width': 9,
          'line-opacity': 0.9,
        },
      });
      this.map.addLayer({
        id: 'route-lines',
        type: 'line',
        source: 'collection-routes',
        paint: {
          'line-color': '#6566f6',
          'line-width': 5,
          'line-opacity': 0.88,
        },
      });
      this.map.on('mouseenter', 'route-lines', () => {
        if (this.map) this.map.getCanvas().style.cursor = 'pointer';
      });
      this.map.on('mouseleave', 'route-lines', () => {
        if (this.map) this.map.getCanvas().style.cursor = '';
      });
      this.map.on('click', 'route-lines', (event) => {
        const routeId = event.features?.[0]?.properties?.['id'];
        if (typeof routeId === 'string') this.selectRoute(routeId);
      });
    }

    this.updateSelectedRouteOnMap(true);
  }

  private updateSelectedRouteOnMap(fitRoute: boolean): void {
    const route = this.selectedRoute();
    if (!this.map || !this.mapReady() || !route) {
      return;
    }

    this.map.setPaintProperty('route-lines', 'line-color', [
      'case',
      ['==', ['get', 'id'], route.id],
      '#020363',
      '#a7a8f8',
    ]);
    this.map.setPaintProperty('route-lines', 'line-width', [
      'case',
      ['==', ['get', 'id'], route.id],
      7,
      4,
    ]);
    this.updateEndpointMarkers(route);

    if (fitRoute) {
      const bounds = new LngLatBounds();
      route.geometry.coordinates.forEach((coordinate) => {
        bounds.extend([coordinate[0], coordinate[1]]);
      });
      this.map.fitBounds(bounds, {
        padding: 55,
        duration: 700,
        maxZoom: 15,
      });
    }
  }

  private updateEndpointMarkers(route: RouteView): void {
    if (!this.map) return;
    const coordinates = route.geometry.coordinates;
    const points: FeatureCollection<Point> = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { kind: 'Inicio' },
          geometry: { type: 'Point', coordinates: coordinates[0] },
        },
        {
          type: 'Feature',
          properties: { kind: 'Fin' },
          geometry: {
            type: 'Point',
            coordinates: coordinates[coordinates.length - 1],
          },
        },
      ],
    };
    const source = this.map.getSource('route-points') as GeoJSONSource | undefined;
    if (source) {
      source.setData(points);
      return;
    }
    this.map.addSource('route-points', { type: 'geojson', data: points });
    this.map.addLayer({
      id: 'route-points',
      type: 'circle',
      source: 'route-points',
      paint: {
        'circle-radius': 7,
        'circle-color': [
          'case',
          ['==', ['get', 'kind'], 'Inicio'],
          '#6566f6',
          '#020363',
        ],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 3,
      },
    });
  }

  private toFeatureCollection(routes: readonly RouteView[]): RoutesCollection {
    return {
      type: 'FeatureCollection',
      features: routes.map((route): Feature<LineString, GeoJsonRouteProperties> => ({
        type: 'Feature',
        properties: {
          id: route.id,
          code: route.code,
          name: route.name,
          sector: route.sector,
        },
        geometry: route.geometry,
      })),
    };
  }
}
