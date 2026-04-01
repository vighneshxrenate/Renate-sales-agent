FROM mcr.microsoft.com/playwright:v1.52.0-noble

WORKDIR /app

RUN npm init -y && npm install playwright@1.52.0

EXPOSE 3000

CMD ["npx", "playwright", "launch-server", "--browser", "chromium", "--host", "0.0.0.0", "--port", "3000"]
