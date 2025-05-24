# 构建阶段
FROM node:20-alpine AS build
WORKDIR /app
COPY alas-system-frontend/ .
ARG BACKEND_API_BASE_URL
ENV BACKEND_API_BASE_URL=${BACKEND_API_BASE_URL}
RUN npm install && npm run build

# 用 Node.js 提供静态文件服务
FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/dist .
RUN npm install -g serve
EXPOSE 4173
CMD ["serve", "-s", ".", "-l", "4173"]
