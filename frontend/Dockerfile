FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG ADMIN_API_KEY=change-me-local-only
RUN npm run build -- --configuration production
RUN ADMIN_API_KEY="${ADMIN_API_KEY}" node -e 'const fs = require("node:fs"); fs.writeFileSync("dist/frontend/browser/app-config.js", "window.AXM_CONFIG = { adminApiKey: " + JSON.stringify(process.env.ADMIN_API_KEY) + " };\n");'

FROM nginx:stable-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 80
