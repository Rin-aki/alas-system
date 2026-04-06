# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY alas-system-frontend/ .

ARG VITE_API_BASE_URL
ARG VITE_WS_FIX_URL
ARG VITE_SCRCPY_BASE_URL
ARG VITE_ALAS_BASE_URL

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_WS_FIX_URL=${VITE_WS_FIX_URL}
ENV VITE_SCRCPY_BASE_URL=${VITE_SCRCPY_BASE_URL}
ENV VITE_ALAS_BASE_URL=${VITE_ALAS_BASE_URL}

RUN npm install && npm run build

# Serve static files
FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/dist .
RUN npm install -g serve
EXPOSE 4173
CMD ["serve", "-s", ".", "-l", "4173"]
