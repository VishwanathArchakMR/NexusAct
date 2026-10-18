FROM caddy:2.9-alpine
# This service is built with Railway Root Directory set to /gateway,
# so the build context contains this service's own Caddyfile.
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
