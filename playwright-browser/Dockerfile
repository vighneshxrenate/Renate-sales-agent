FROM mcr.microsoft.com/playwright:v1.58.0-noble

WORKDIR /app

RUN npm init -y && npm install playwright@1.58.0

COPY server.js .

EXPOSE 3000

CMD ["node", "server.js"]
