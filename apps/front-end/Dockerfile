FROM node:22-alpine AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json ./
RUN npm install

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG API_PROXY_TARGET=http://api:2000
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
ENV NEXT_PUBLIC_API_PROXY_PREFIX=/proxy
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=2002
ENV HOSTNAME=0.0.0.0
ENV API_PROXY_TARGET=http://api:2000
ENV NEXT_PUBLIC_API_PROXY_PREFIX=/proxy
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 2002
CMD ["node", "server.js"]
