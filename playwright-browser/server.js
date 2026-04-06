const { chromium } = require("playwright");

(async () => {
  const server = await chromium.launchServer({
    host: "0.0.0.0",
    port: 3000,
    wsPath: "/ws",
    headless: false,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-blink-features=AutomationControlled",
      "--disable-infobars",
      "--window-size=1920,1080",
      "--start-maximized",
      "--headless=new",
    ],
    ignoreDefaultArgs: ["--enable-automation"],
  });
  console.log(`Playwright WebSocket: ${server.wsEndpoint()}`);
})();
