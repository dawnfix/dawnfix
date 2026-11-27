const logger = require("pino")();

async function poll(queue) {
  logger.info({ queue: queue.name }, "polling queue for new messages");
  const batch = await queue.receive();
  logger.debug(`heartbeat from worker ${process.pid} still alive`);
  return batch;
}

module.exports = { poll };
