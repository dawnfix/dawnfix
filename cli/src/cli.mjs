// dawnfix: the npm command. `init` and `doctor` set up and check Dawnfix in a repo; `flare`
// is Dawnfix Flare's CLI (flare/src/main.ts), bundled in.
import { main as flare } from '../../flare/src/main.ts';
import { doctor } from './doctor.mjs';
import { init } from './init.mjs';
import { VERSION } from './version.mjs';

export const HELP = `Dawnfix ${VERSION}: the AI SRE that runs in your own GitHub Actions or GitLab CI.
Source available under FSL-1.1-ALv2. https://dawnfix.dev

Usage: npx dawnfix <command> [options]

Commands:
  init        Set Dawnfix up in this repo: .dawnfix.yml and a 15-line workflow that calls
              dawnfix/dawnfix/.github/workflows/dawnfix.yml (or, with --host gitlab, a
              .gitlab-ci.yml that includes the pinned template). Shows both before writing.
  doctor      Check the setup: the config, the pinned workflow, secret and variable
              names, Free or Enterprise.
  flare ...   Dawnfix Flare: read-only audit of Cloudflare accounts and Workers
              (npx dawnfix flare --help).

Options:
  -v, --version   Print the version
  -h, --help      This help (and <command> --help)

The Python tools (dawnfix, logbill, parity, sweeper, leastpriv, receipt, fleet) are the
PyPI package of the same version: pipx install dawnfix==${VERSION}
`;

export async function run(argv, io) {
  const [cmd, ...rest] = argv;
  if (!cmd || cmd === '-h' || cmd === '--help' || cmd === 'help') {
    io.stdout(HELP);
    return cmd ? 0 : 2;
  }
  if (cmd === '-v' || cmd === '--version' || cmd === 'version') {
    io.stdout(`${VERSION}\n`);
    return 0;
  }
  if (cmd === 'init') return init(rest, io);
  if (cmd === 'doctor') return doctor(rest, io);
  if (cmd === 'flare') return flare(rest, io);
  io.stderr(`dawnfix: unknown command ${JSON.stringify(cmd)}\n\n${HELP}`);
  return 2;
}

const io = {
  env: process.env,
  fetch: globalThis.fetch,
  stdout: (s) => process.stdout.write(s),
  stderr: (s) => process.stderr.write(s),
  now: () => new Date(),
  isTTY: Boolean(process.stdin.isTTY && process.stdout.isTTY),
  ...(process.stdout.columns ? { columns: process.stdout.columns } : {}),
  cwd: process.cwd(),
  stdin: process.stdin,
  stdoutStream: process.stdout,
};

run(process.argv.slice(2), io).then(
  (code) => {
    process.exitCode = code;
  },
  (e) => {
    process.stderr.write(`dawnfix: ${e instanceof Error ? e.message : String(e)}\n`);
    process.exitCode = 2;
  },
);
