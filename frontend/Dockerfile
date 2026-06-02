# Multi-stage production build: Vite → static → nginx.
# Final image serves the SPA on port 80, no Node runtime needed at runtime.

# ---------- stage 1: build ----------
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
# VITE_API_BASE_URL is baked into the static bundle at build time.
# Browser hits localhost:8000/api/v1 directly (backend container exposes that port).
ENV VITE_API_BASE_URL=http://localhost:8000/api/v1
RUN npm run build

# ---------- stage 2: serve ----------
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
CMD ["nginx", "-g", "daemon off;"]
