# Stage 1: Build static bundle
FROM node:22-alpine AS builder

WORKDIR /app
COPY services/web/package*.json ./
RUN npm ci

COPY services/web ./
RUN npm run build

# Stage 2: Serve via NGINX with strict security headers
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY services/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
