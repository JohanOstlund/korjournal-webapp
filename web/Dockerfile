FROM node:20-alpine AS base

# --- Build stage ---
FROM base AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=__NEXT_PUBLIC_API_URL__
RUN npm run build

# --- Production stage ---
FROM base AS runner
WORKDIR /app

LABEL org.opencontainers.image.title="Korjournal Web" \
      org.opencontainers.image.description="Körjournal frontend – Next.js. Kräver korjournal-api på port 8080." \
      org.opencontainers.image.source="https://github.com/JohanOstlund/korjournal-webapp"

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=http://localhost:8080

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["./entrypoint.sh"]
CMD ["node", "server.js"]
