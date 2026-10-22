# ==============================================================================
# CircuitSight — Frontend Production Dockerfile (Multi-Stage Node / Nginx)
#
# Build Context: ./frontend
# Build Command: docker build -f frontend/Dockerfile -t circuitsight-frontend:latest ./frontend
#
# Architecture:
# - Stage 1 (build): Node.js 20 Alpine compiles React/Tailwind/Vite into static assets
# - Stage 2 (runtime): Nginx Alpine serves static files with SPA routing fallback
#
# Safeguards:
# - Uses relative API path (/api) to avoid hardcoded hostnames, IPs, or domains
# - SPA routing fallback (try_files $uri $uri/ /index.html) prevents 404s on refresh
# - client_max_body_size set to 50M to match backend detection upload limits
# - Pre-installs clean dependencies via npm ci (local node_modules excluded by .dockerignore)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build static assets with Node.js
# ------------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests first to leverage Docker layer caching
COPY package.json package-lock.json ./

# Clean installation of dependencies
RUN npm ci

# Copy frontend source files (local node_modules/ and dist/ excluded via .dockerignore)
COPY . .

# Compile production bundle into /app/dist
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Serve static production assets with Nginx
# ------------------------------------------------------------------------------
FROM nginx:alpine

# Remove default Nginx welcome site
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled static assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Configure Nginx for SPA fallback, asset caching, and 50MB payload uploads
RUN printf 'server {\n\
    listen 80;\n\
    server_name localhost;\n\
\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    # Allow uploads up to 50MB matching backend PCB inspection limits\n\
    client_max_body_size 50M;\n\
\n\
    # Gzip compression for performance\n\
    gzip on;\n\
    gzip_vary on;\n\
    gzip_min_length 1024;\n\
    gzip_proxied any;\n\
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;\n\
\n\
    # Static asset caching\n\
    location ~* \\.(?:css|js|jpg|jpeg|gif|png|ico|cur|gz|svg|svgz|mp4|ogg|ogv|webm)$ {\n\
        expires 1y;\n\
        access_log off;\n\
        add_header Cache-Control "public, max-age=31536000, immutable";\n\
    }\n\
\n\
    # Single Page Application fallback\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
\n\
    # Reverse proxy for /api to backend service (resolvable via Docker Compose / K8s DNS)\n\
    location /api/ {\n\
        proxy_pass http://backend:8000/api/;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Upgrade $http_upgrade;\n\
        proxy_set_header Connection "upgrade";\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
        proxy_read_timeout 300s;\n\
        proxy_connect_timeout 75s;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

# Container Healthcheck using pre-installed Alpine wget
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
