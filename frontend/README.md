# Frontend

## Integración con Docker Compose

Desde la raíz del repositorio, `docker compose up --build -d` construye y ejecuta la interfaz junto con la API y PostgreSQL. Abre el puerto definido por `FRONTEND_HOST_PORT` en `.env` (4200 por defecto); Nginx sirve Angular y reenvía `/api` al backend configurado en `API_INTERNAL_URL`.

El frontend no contiene credenciales ni claves API. El inicio de sesión se valida en el backend, que entrega una cookie de sesión `HttpOnly`; `ADMIN_API_KEY` se mantiene exclusivamente en los servicios backend y simulador.

## Desarrollo local

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 22.2.4.

## Development server

To start a local development server, run:

```bash
npm start
```

The start script prepares the MapLibre worker asset before launching Angular. Once the server is running, open `http://localhost:4200/`; the application reloads whenever you modify source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
npm run build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
