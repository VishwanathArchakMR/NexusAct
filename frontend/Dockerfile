# ==============================================================================
# NexusAct (GAF) — Frontend Multi-Stage Production Dockerfile
# Stage 1 (builder): Install deps and compile React/TS to static assets.
# Stage 2 (server):  Serve with lightweight nginx:alpine.
# ==============================================================================
# Build:
#   docker build -t nexusact-frontend ./frontend \
#     --build-arg VITE_API_BASE_URL=https://<your-backend-url>
# ==============================================================================

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

# Build-time argument so Vite can embed the backend API URL at compile time.
# Same-origin API by default; public production traffic is routed by the gateway.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

WORKDIR /app

# Cache node_modules layer separately from source code
COPY package.json package-lock.json* ./
RUN npm ci --silent

COPY . .
RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS server

# Custom nginx config: SPA routing fallback + security headers
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA config: all unknown routes return index.html (client-side routing)
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen       80;
    server_name  _;

    root   /usr/share/nginx/html;
    index  index.html;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    # Serve pre-built assets with long cache
    location ~* \.(js|css|png|jpg|jpeg|svg|ico|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback: all unknown paths return index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --spider -q http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
