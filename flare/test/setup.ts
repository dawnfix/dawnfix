// No test may reach the network: the real fetch is replaced with one that fails loudly.
// Every Cloudflare response comes from test/fixtures/cloudflare.ts through an injected fetch.
globalThis.fetch = (async (input: unknown) => {
  throw new Error(`network disabled in tests: ${String(input)}`);
}) as typeof fetch;
