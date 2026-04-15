FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --silent
COPY . .
RUN npm run build

# This image is only for building — nginx/Dockerfile copies from here
FROM scratch
COPY --from=build /app/dist /dist
