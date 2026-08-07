FROM node:20-bookworm-slim

WORKDIR /app

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

ENV NODE_ENV=production

CMD ["sh", "-c", "npx next start -H 0.0.0.0 -p ${PORT:-8080}"]
