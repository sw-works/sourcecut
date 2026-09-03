# Built from the repository root, not from apps/web.
#
# Two pages read committed data outside the app at build time: the Odyssey
# entity page imports `data/reference/odyssey_entities_themes.json`, and the
# landing page reads the captured example board. Building with apps/web as the
# context resolves neither, and the Odyssey import fails the Vite build
# outright.
#
#   gcloud builds submit --config deploy/cloud-run/build-web.yaml \
#     --substitutions "_IMAGE=$SOURCECUT_WEB_IMAGE" .
FROM node:22-slim AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./apps/web/
WORKDIR /app/apps/web
RUN npm ci
WORKDIR /app
COPY apps/web ./apps/web
COPY data/reference ./data/reference
# The example board is optional: index.astro falls back to the empty form when
# it is absent, so a checkout that has never run sourcecut-capture-example
# still builds. The directory is committed so this COPY always resolves.
COPY data/examples ./data/examples
WORKDIR /app/apps/web
RUN npm run build

FROM node:22-slim
ENV NODE_ENV=production PORT=8080 HOST=0.0.0.0
WORKDIR /app
# `dist` alone does not run. Astro's node build leaves some dependencies
# external — `piccolore` is imported straight out of a server chunk — so the
# entrypoint dies with ERR_MODULE_NOT_FOUND before it ever binds PORT, which
# Cloud Run reports only as "container failed to start".
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /app/apps/web/dist ./dist
EXPOSE 8080
CMD ["node", "./dist/server/entry.mjs"]
