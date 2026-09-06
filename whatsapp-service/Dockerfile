FROM node:20-slim
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --production
COPY service.js ./
EXPOSE 3001
CMD ["node", "service.js"]
