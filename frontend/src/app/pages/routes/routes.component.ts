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
  Map as GLMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
  StyleSpecification,
} from 'maplibre-gl';
import { firstValueFrom } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import {
  CitizenRoutesService,
  ETAResponse,
  LiveVehicle,
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

  protected readonly Math = Math;
  protected readonly routes = signal<readonly RouteView[]>([]);
  protected readonly selectedRouteId = signal('');
  protected readonly loading = signal(true);
  protected readonly mapReady = signal(false);
  protected readonly usingLocalData = signal(true);
  protected readonly liveVehicles = signal<readonly LiveVehicle[]>([]);
  protected readonly liveVehicleError = signal('');
  protected readonly eta = signal<ETAResponse | null>(null);
  protected readonly etaError = signal('');
  protected readonly etaLoading = signal(false);
  protected readonly locationLoading = signal(false);
  protected readonly citizenLocation = signal<[number, number] | null>(null);
  protected readonly selectedRoute = computed(
    () =>
      this.routes().find((route) => route.id === this.selectedRouteId()) ??
      null,
  );

  private readonly routeService = inject(CitizenRoutesService);
  private readonly fallbackUrl = '/map-data/rutas.geojson';
  private map?: GLMap;
  private liveVehiclesTimer?: number;
  private readonly vehicleMarkers = new Map<string, Marker>();

  ngOnInit(): void {
    void this.loadRoutes();
  }

  ngAfterViewInit(): void {
    this.initializeMap();
    void this.refreshLiveVehicles();
    this.liveVehiclesTimer = window.setInterval(
      () => void this.refreshLiveVehicles(),
      5000,
    );
  }

  ngOnDestroy(): void {
    if (this.liveVehiclesTimer !== undefined) {
      window.clearInterval(this.liveVehiclesTimer);
    }
    this.vehicleMarkers.forEach((marker) => marker.remove());
    this.vehicleMarkers.clear();
    this.map?.remove();
  }

  protected selectRoute(routeId: string): void {
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

  protected async requestEtaForMapPoint(): Promise<void> {
    const location = this.citizenLocation();
    if (!location) {
      this.etaError.set('Haz clic en el mapa o usa tu ubicación para consultar la ETA.');
      return;
    }
    await this.requestEta(location[1], location[0]);
  }

  protected async requestEtaForCurrentLocation(): Promise<void> {
    if (!navigator.geolocation) {
      this.etaError.set('Este navegador no permite consultar la ubicación.');
      return;
    }
    this.locationLoading.set(true);
    this.etaError.set('');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        this.setCitizenLocation(longitude, latitude);
        this.map?.flyTo({
          center: [longitude, latitude],
          zoom: 16,
          duration: 700,
        });
        this.locationLoading.set(false);
        void this.requestEta(latitude, longitude);
      },
      (error) => {
        this.etaError.set(
          error.code === error.PERMISSION_DENIED
            ? 'Permiso de ubicación denegado. Haz clic en el mapa para elegir un punto.'
            : 'No fue posible obtener tu ubicación. Intenta de nuevo o elige un punto en el mapa.',
        );
        this.locationLoading.set(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  protected centerSelectedRoute(): void {
    this.updateSelectedRouteOnMap(true);
  }

  protected centerLiveVehicle(): void {
    const selectedVehicle =
      this.liveVehicles().find(
        (vehicle) => vehicle.route_id === this.selectedRouteId(),
      ) ?? this.liveVehicles()[0];
    if (!selectedVehicle) return;
    this.map?.flyTo({
      center: [selectedVehicle.longitude, selectedVehicle.latitude],
      zoom: 16,
      duration: 700,
    });
  }

  protected etaStatusLabel(status: ETAResponse['status']): string {
    return {
      approaching: 'En camino',
      arriving: 'Está llegando',
      passed: 'El camión ya pasó',
      not_started: 'Jornada por iniciar',
      cancelled: 'Servicio cancelado',
      scheduled: 'Estimación programada',
    }[status];
  }

  protected formatEtaTime(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'America/Bogota',
    }).format(new Date(value));
  }

  protected formatRemainingDistance(value: number | null): string {
    if (value === null) return 'No disponible';
    return value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m`;
  }

  private async requestEta(latitude: number, longitude: number): Promise<void> {
    this.etaLoading.set(true);
    this.etaError.set('');
    this.eta.set(null);
    try {
      const result = await firstValueFrom(this.routeService.getEta(latitude, longitude));
      this.eta.set(result);
    } catch (error) {
      this.etaError.set(
        error instanceof HttpErrorResponse && error.status === 404
          ? 'No hay una ruta activa cercana a este punto. Selecciona una ubicación sobre el recorrido.'
          : 'No fue posible consultar la ETA. Verifica la conexión con el servicio.',
      );
    } finally {
      this.etaLoading.set(false);
    }
  }

  private async refreshLiveVehicles(): Promise<void> {
    try {
      const vehicles = await firstValueFrom(this.routeService.listLiveVehicles());
      const recentVehicles = [
        ...new Map(
          vehicles
            .filter((vehicle) => !vehicle.stale)
            .map((vehicle) => [vehicle.truck_plate, vehicle]),
        ).values(),
      ];
      this.liveVehicles.set(recentVehicles);
      this.liveVehicleError.set('');
      this.updateVehicleMarkers(recentVehicles);
    } catch {
      this.liveVehicles.set([]);
      this.liveVehicleError.set('No se pudo consultar la ubicación de los camiones.');
      this.updateVehicleMarkers([]);
    }
  }

  private updateVehicleMarkers(vehicles: readonly LiveVehicle[]): void {
    const currentPlates = new Set(vehicles.map((vehicle) => vehicle.truck_plate));
    for (const [plate, marker] of this.vehicleMarkers) {
      if (!currentPlates.has(plate)) {
        marker.remove();
        this.vehicleMarkers.delete(plate);
      }
    }
    if (!this.map) return;
    for (const vehicle of vehicles) {
      let marker = this.vehicleMarkers.get(vehicle.truck_plate);
      if (!marker) {
        const element = document.createElement('div');
        element.className = 'vehicle-marker';
        element.setAttribute('aria-label', `Camión ${vehicle.truck_name}, simulación`);
        element.dataset['plate'] = vehicle.truck_plate;
        element.title = `${vehicle.truck_name} · ${vehicle.truck_plate} · GPS simulado`;
        const icon = document.createElement('span');
        icon.textContent = '🚛';
        element.append(icon);
        marker = new Marker({
          element,
          anchor: 'center',
          rotationAlignment: 'viewport',
        })
          .setLngLat([vehicle.longitude, vehicle.latitude])
          .addTo(this.map);
        this.vehicleMarkers.set(vehicle.truck_plate, marker);
      }
      marker.setLngLat([vehicle.longitude, vehicle.latitude]);
      marker
        .getElement()
        .style.setProperty('--vehicle-heading', `${vehicle.heading ?? 0}deg`);
    }
  }

  private setCitizenLocation(longitude: number, latitude: number): void {
    this.citizenLocation.set([longitude, latitude]);
    this.etaError.set('');
    this.eta.set(null);
    this.updateCitizenLocationOnMap();
  }

  private updateCitizenLocationOnMap(): void {
    const source = this.map?.getSource('citizen-location') as
      | GeoJSONSource
      | undefined;
    if (!source) return;
    const location = this.citizenLocation();
    const data: FeatureCollection<Point> = {
      type: 'FeatureCollection',
      features: location
        ? [
            {
              type: 'Feature',
              properties: {},
              geometry: { type: 'Point', coordinates: location },
            },
          ]
        : [],
    };
    source.setData(data);
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
    const now = new Date();
    const currentDate = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: 'America/Bogota',
    }).format(now);
    const currentTime = new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
      timeZone: 'America/Bogota',
    }).format(now);
    const routes = collection.features.map((feature) => {
      const properties = feature.properties;
      const upcomingSchedules = schedules.filter(
        (schedule) =>
          schedule.route_id === properties.id &&
          (schedule.service_date > currentDate ||
            (schedule.service_date === currentDate &&
              schedule.expected_end_time > currentTime)),
      );
      return {
        ...properties,
        description:
          details?.find((detail) => detail.id === properties.id)?.description ??
          null,
        geometry: feature.geometry,
        schedule:
          upcomingSchedules.find((schedule) => !schedule.cancelled) ??
          upcomingSchedules[0] ??
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

    setWorkerUrl('/maplibre-gl-worker.js');

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

    this.map = new GLMap({
      container: this.mapContainer.nativeElement,
      style,
      center: [-75.6811, 4.5339],
      zoom: 12,
      minZoom: 10,
      maxZoom: 18,
    });
    this.map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    this.map.once('style.load', () => {
      this.mapReady.set(true);
      this.renderRoutes(this.toFeatureCollection(this.routes()));
      this.map?.addSource('citizen-location', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      });
      this.map?.addLayer({
        id: 'citizen-location',
        type: 'circle',
        source: 'citizen-location',
        paint: {
          'circle-radius': 7,
          'circle-color': '#d94b35',
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 3,
        },
      });
      this.updateCitizenLocationOnMap();
      this.map?.on('click', (event) => {
        this.setCitizenLocation(event.lngLat.lng, event.lngLat.lat);
      });
      this.updateVehicleMarkers(this.liveVehicles());
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
        padding: 72,
        duration: 700,
        maxZoom: 16,
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
