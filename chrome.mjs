import fs from 'fs';

const CHROME_CANDIDATES = {
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ],
  linux: [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ],
};

export function launchOptions() {
  if (process.env.CHROME_PATH) {
    console.log('Using CHROME_PATH', process.env.CHROME_PATH);
    return { executablePath: process.env.CHROME_PATH };
  }
  if (process.env.CHROME_CHANNEL) {
    console.log('Using CHROME_CHANNEL', process.env.CHROME_CHANNEL);
    return { channel: process.env.CHROME_CHANNEL };
  }
  for (const p of CHROME_CANDIDATES[process.platform] || []) {
    if (fs.existsSync(p)) {
      console.log('Using Chrome at', p);
      return { executablePath: p };
    }
  }
  console.log('Using Playwright Chromium');
  return {};
}
