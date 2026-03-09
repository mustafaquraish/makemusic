// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 0,
  use: {
    browserName: 'chromium',
    headless: true,
    viewport: { width: 1280, height: 800 },
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
  webServer: {
    command: 'python3 -m http.server 8574 --bind 127.0.0.1',
    port: 8574,
    reuseExistingServer: true,
  },
});
