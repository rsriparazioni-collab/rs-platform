FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json ./
RUN yarn install --network-timeout 600000
COPY frontend/ .
ENV REACT_APP_BACKEND_URL=http://localhost:8080
RUN yarn build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY deploy-locale/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
