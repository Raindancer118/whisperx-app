# ── Stage 1: Build React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend_build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: nginx with built frontend ───────────────────────────────────
FROM nginx:1.27-alpine
COPY --from=frontend_build /app/dist /var/www/html
COPY nginx/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
