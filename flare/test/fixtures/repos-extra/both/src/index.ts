export default {
  async fetch(request: Request): Promise<Response> {
    return new Response(new URL(request.url).pathname);
  },
  async scheduled(): Promise<void> {},
};
