FROM node:24.22.2-alpine3.23 AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY design/tokens.css /app/design/tokens.css
RUN npm run build

FROM caddy:2.11.9-alpine
COPY --from=build /app/frontend/dist/ /srv/web/
COPY frontend/Caddyfile /etc/caddy/Caddyfile
EXPOSE 80 443
