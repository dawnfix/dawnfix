// Every product name, org and URL the tool prints lives here and nowhere else, so a rename
// is one file. Renamed from Dawnpatch Flare on 27 Nov 2026.

const SITE = 'https://dawnfix.dev';

export const BRAND = {
  suite: 'Dawnfix',
  product: 'Flare',
  fullName: 'Dawnfix Flare',
  cli: 'flare',
  org: 'Dawnfix',
  homepage: `${SITE}/flare`,
  docsUrl: `${SITE}/flare#run`,
  checksUrl: `${SITE}/flare#checks`,
  userAgent: 'dawnfix-flare/0.1 (read-only audit)',
  /**
   * The closing line of a scan (`--json` carries it as `pitch`): the free daily workflow in
   * the customer's own CI, and the one hosted extra. No prices: Enterprise is "Contact us".
   */
  pitch: {
    line: 'Run this audit every day in your own GitHub Actions, free: templates/github/workflows/dawnfix-flare.yml in the Dawnfix repo. Your Cloudflare token stays a GitHub secret. An email the morning a new exposure appears is Dawnfix Enterprise.',
    url: `${SITE}/flare#daily`,
  },
} as const;

export const CLOUDFLARE_API = 'https://api.cloudflare.com/client/v4';
