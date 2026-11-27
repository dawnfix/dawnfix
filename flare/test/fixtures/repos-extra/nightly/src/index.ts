export default {
  async scheduled(_event: unknown, env: { URL: string }): Promise<void> {
    // A call to fetch is not a fetch handler.
    await fetch(env.URL, { method: 'POST' });
  },
};
