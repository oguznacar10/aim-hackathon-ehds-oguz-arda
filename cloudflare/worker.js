// One container instance ("demo") serves every request; the Durable Object starts it on first use.
const PORT = 8000;

export class Gatekeeper {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }

  async fetch(request) {
    const container = this.ctx.container;
    if (!container.running) {
      container.start({
        enableInternet: true,
        env: {
          HOST: "0.0.0.0",
          PORT: String(PORT),
          GATEKEEPER_SECOND_OPINION: "jev",
          // only keys the Worker has, so an empty string never masks a container-level variable
          ...(this.env.OPENROUTER_API_KEY ? { OPENROUTER_API_KEY: this.env.OPENROUTER_API_KEY } : {}),
          ...(this.env.TYPESAFE_API_KEY ? { TYPESAFE_API_KEY: this.env.TYPESAFE_API_KEY } : {}),
        },
      });
    }
    const port = container.getTcpPort(PORT);
    const url = new URL(request.url);
    const target = `http://container${url.pathname}${url.search}`;
    let lastError;
    for (let attempt = 0; attempt < 30; attempt++) {
      try {
        return await port.fetch(target, request);
      } catch (e) {
        lastError = e;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    return new Response(`The app is still starting: ${lastError}`, { status: 503 });
  }
}

export default {
  fetch(request, env) {
    const id = env.GATEKEEPER.idFromName("demo");
    return env.GATEKEEPER.get(id).fetch(request);
  },
};
