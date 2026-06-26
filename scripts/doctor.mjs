#!/usr/bin/env node
// Preflight environment check — runs automatically before `pnpm dev`.
// Surfaces every common starter-kit setup gotcha *before* uvicorn or
// next try to start, with actionable error messages.
//
// Zero dependencies (uses only node:* core modules) so this works on a
// fresh clone before anyone has run `pnpm install`.
//
// Run directly:  node scripts/doctor.mjs
// Run via pnpm:  pnpm doctor

import { copyFileSync, existsSync, readFileSync } from "node:fs";
import { createServer } from "node:net";
import { execSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ENV_FILE = resolve(REPO_ROOT, ".env");
const ENV_EXAMPLE = resolve(REPO_ROOT, ".env.example");
const VENV_UVICORN = resolve(REPO_ROOT, "services/api/.venv/bin/uvicorn");

// Common bin dirs the doctor scans when a required tool isn't on PATH.
// Lets us distinguish "not installed" from "installed but shell can't see it"
// — a common gotcha on Apple Silicon when /opt/homebrew/bin isn't on PATH
// for non-interactive child shells.
const KNOWN_BIN_DIRS = [
  "/opt/homebrew/bin", // Apple Silicon Homebrew
  "/opt/homebrew/sbin",
  "/usr/local/bin", // Intel Homebrew + manual installs
  "/usr/local/sbin",
  "/opt/local/bin", // MacPorts
  resolve(process.env.HOME ?? "/", ".local/bin"), // pip --user / pipx
];

// Required minimum versions. Bump as upstream support shifts.
const REQUIRED_NODE_MAJOR = 20;
const REQUIRED_PNPM_MAJOR = 9;
const REQUIRED_PYTHON_MINOR = 11; // 3.11+

// Required B2 env vars + the exact placeholder strings shipped in
// .env.example. Keep in sync with services/api/main.py REQUIRED_B2_SETTINGS
// and PLACEHOLDER_VALUES.
const STANDARD_B2_KEY_ID = "B2_APPLICATION_KEY_ID";
const LEGACY_B2_KEY_ID = "B2_KEY_ID";
const REQUIRED_B2_VARS = [
  "B2_REGION",
  "B2_APPLICATION_KEY",
  "B2_BUCKET_NAME",
];
const PLACEHOLDERS = new Set([
  "your_application_key_id",
  "your_key_id",
  "your_b2_region",
  "your_application_key",
  "your-bucket-name",
]);

// System binaries the pipeline shells out to via the shell PATH.
// `versionArg` matters: ffmpeg/ffprobe use BSD-style single-dash flags
// only — `--version` (double dash) parses as "-v ersion" and exits 8.
// yt-dlp is NOT here — it's a Python module invoked as `python -m yt_dlp`
// inside the API venv, checked separately by checkVenvPythonModules().
const REQUIRED_TOOLS = [
  { bin: "ffmpeg", versionArg: "-version", hint: "Install ffmpeg: `brew install ffmpeg` (macOS) or `apt-get install ffmpeg` (Debian/Ubuntu)" },
  { bin: "ffprobe", versionArg: "-version", hint: "ffprobe ships with ffmpeg — installing ffmpeg gives you both" },
];

// Python modules the API venv must be able to import. These are pip-installed
// inside services/api/.venv and invoked via the venv's Python interpreter,
// so we probe them with `services/api/.venv/bin/python -c "import ..."`
// rather than trying to find them on the shell PATH.
const REQUIRED_VENV_MODULES = [
  {
    module: "yt_dlp",
    hint: "Run: `cd services/api && .venv/bin/pip install -e .` (or `pip install yt-dlp`)",
  },
];

// Only Next.js: `pnpm dev` self-heals the API side via scripts/pick-port.mjs,
// so warning about 8000 here would just duplicate dev.sh's own banner.
const PORTS_TO_CHECK = [{ port: 3000, name: "Next.js dev server" }];

const failures = [];
const warnings = [];

function fail(msg, fix) {
  failures.push({ msg, fix });
}

function warn(msg, fix) {
  warnings.push({ msg, fix });
}

function tryExec(cmd) {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

// Exit-code-based probe — does NOT rely on stdout content. Required for
// tools like ffmpeg/ffprobe that print their version banner to stderr,
// which tryExec() above silently drops.
function exitsZero(cmd) {
  try {
    execSync(cmd, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function parseSemver(s) {
  // Pulls "v20.10.0" / "20.10.0" / "9.15.0" / "Python 3.13.5" — lenient.
  const match = s.match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return { major: +match[1], minor: +match[2], patch: +match[3] };
}

// ----- Tool versions -----

function checkNode() {
  const v = parseSemver(process.version);
  if (!v || v.major < REQUIRED_NODE_MAJOR) {
    fail(
      `Node ${process.version} is too old (need >= ${REQUIRED_NODE_MAJOR}.0.0)`,
      `Install a current Node via nvm/fnm: \`nvm install ${REQUIRED_NODE_MAJOR}\``,
    );
  }
}

function checkPnpm() {
  const out = tryExec("pnpm --version");
  if (!out) {
    fail("pnpm is not installed", "Install via corepack: `corepack enable && corepack prepare pnpm@latest --activate`");
    return;
  }
  const v = parseSemver(out);
  if (!v || v.major < REQUIRED_PNPM_MAJOR) {
    fail(
      `pnpm ${out} is too old (need >= ${REQUIRED_PNPM_MAJOR})`,
      `Run: \`corepack prepare pnpm@latest --activate\``,
    );
  }
}

function checkPython() {
  // Try python3 first (canonical on macOS/Linux), then versioned names that
  // Homebrew installs (python3.13, python3.12, python3.11), then the bare
  // python shim (Windows / pyenv). Stop at the first one that satisfies the
  // minimum version — this avoids false failures on macOS where `python3`
  // resolves to the system 3.9 even when a newer Homebrew Python is on PATH.
  const candidates = [
    "python3",
    "python3.13",
    "python3.12",
    "python3.11",
    "python",
  ];
  for (const bin of candidates) {
    const out = tryExec(`${bin} --version`);
    if (!out) continue;
    const v = parseSemver(out);
    if (v && v.major >= 3 && v.minor >= REQUIRED_PYTHON_MINOR) return; // good
  }
  // Nothing suitable found — report using the first candidate that exists.
  const found = candidates.map((b) => tryExec(`${b} --version`)).find(Boolean);
  if (found) {
    fail(
      `${found} is too old (need >= 3.${REQUIRED_PYTHON_MINOR})`,
      `Install Python 3.${REQUIRED_PYTHON_MINOR}+ via Homebrew (\`brew install python@3.12\`) or pyenv (\`pyenv install 3.${REQUIRED_PYTHON_MINOR}\`)`,
    );
  } else {
    fail(
      "Python is not on PATH",
      `Install Python 3.${REQUIRED_PYTHON_MINOR}+ from https://python.org, via Homebrew (\`brew install python@3.12\`), or pyenv`,
    );
  }
}

// ----- Project state -----

function checkVenv() {
  if (!existsSync(VENV_UVICORN)) {
    fail(
      "Backend virtualenv not set up (services/api/.venv/bin/uvicorn missing)",
      "Run: `cd services/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cd ../..`",
    );
  }
}

function parseEnvFile(path) {
  // Minimal .env parser — enough for KEY=value lines, ignores comments
  // and quoted strings. We don't need the full dotenv grammar here.
  const out = {};
  const text = readFileSync(path, "utf8");
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function checkEnv() {
  if (!existsSync(ENV_FILE)) {
    // Auto-bootstrap from the template so the user has one less manual step.
    // The placeholder check below still fails until they actually edit it.
    if (existsSync(ENV_EXAMPLE)) {
      copyFileSync(ENV_EXAMPLE, ENV_FILE);
      warn(
        ".env was missing — copied from .env.example",
        "Edit .env and replace placeholders with your real B2 credentials before the next run",
      );
    } else {
      fail(
        ".env is missing and .env.example wasn't found to copy from",
        "Restore .env.example from git, or create .env by hand with the B2 keys",
      );
      return;
    }
  }
  const env = parseEnvFile(ENV_FILE);
  const missing = REQUIRED_B2_VARS.filter((k) => !env[k]);
  if (!env[STANDARD_B2_KEY_ID] && !env[LEGACY_B2_KEY_ID]) {
    missing.unshift(`${STANDARD_B2_KEY_ID} (or ${LEGACY_B2_KEY_ID} during rollout)`);
  }
  if (missing.length > 0) {
    fail(
      `.env is missing required B2 variables: ${missing.join(", ")}`,
      "See .env.example for the full list and edit .env to add them",
    );
  }
  const placeholders = [
    STANDARD_B2_KEY_ID,
    LEGACY_B2_KEY_ID,
    ...REQUIRED_B2_VARS,
  ].filter(
    (k) => env[k] && PLACEHOLDERS.has(env[k]),
  );
  if (placeholders.length > 0) {
    fail(
      `.env still has placeholder values: ${placeholders.join(", ")}`,
      "Edit .env and replace placeholders with your real B2 credentials (https://secure.backblaze.com/app_keys.htm?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=video-to-insights-pipeline)",
    );
  }
  if (!env[STANDARD_B2_KEY_ID] && env[LEGACY_B2_KEY_ID]) {
    warn(
      `${LEGACY_B2_KEY_ID} is being used as a temporary migration fallback`,
      `add ${STANDARD_B2_KEY_ID} before removing legacy B2 variables after old processes drain`,
    );
  }
  // Soft signal: graceful degradation lets the pipeline run without
  // NVIDIA, but most users will want the analysis half.
  if (!env.NVIDIA_API_KEY) {
    warn(
      "NVIDIA_API_KEY is not set",
      "ok — the pipeline still uploads source video to B2 and finishes with status `done_no_analysis`. To enable transcription + insights, get a free key at https://build.nvidia.com/ and add it to .env",
    );
  }
}

// Look for `bin` in well-known install locations. Returns the absolute path
// if found, else null. Used to tell "missing" apart from "installed but the
// shell that spawned me can't see it" — the latter is the most common
// Apple-Silicon-Homebrew gotcha.
function findOnDisk(bin) {
  for (const dir of KNOWN_BIN_DIRS) {
    const candidate = resolve(dir, bin);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

function checkTools() {
  for (const tool of REQUIRED_TOOLS) {
    // Exit-code probe — ffmpeg/ffprobe write the banner to stderr and
    // leave stdout empty, so a stdout-truthy check would misread them as
    // "not installed." Version flag is per-tool because ffmpeg/ffprobe
    // reject `--version`.
    if (exitsZero(`${tool.bin} ${tool.versionArg}`)) continue;

    const onDisk = findOnDisk(tool.bin);
    if (onDisk) {
      const dir = dirname(onDisk);
      const onPath = (process.env.PATH ?? "").split(":").includes(dir);
      if (onPath) {
        // dir is on PATH but `bin --version` still fails. Likely broken
        // symlink, missing dyld dep, wrong arch, or macOS quarantine.
        fail(
          `${tool.bin} exists at ${onDisk} but won't run (--version failed)`,
          `Try: \`${onDisk} -version\` to see the real error. Common causes: macOS quarantine (\`xattr -d com.apple.quarantine ${onDisk}\`), missing dynamic libs, or wrong CPU arch — reinstall via \`brew reinstall ${tool.bin}\``,
        );
      } else {
        fail(
          `${tool.bin} is installed at ${onDisk} but ${dir} is not on this shell's PATH`,
          `Open a new terminal, or run \`eval "$(/opt/homebrew/bin/brew shellenv)"\` (Homebrew), or append \`export PATH="${dir}:$PATH"\` to ~/.zshrc and \`source ~/.zshrc\``,
        );
      }
    } else {
      fail(`${tool.bin} is not installed`, tool.hint);
    }
  }
}

function checkVenvPythonModules() {
  // If the venv itself is missing, checkVenv() already reported it. Skip
  // these imports rather than emit a noisy follow-on error.
  const venvPython = resolve(REPO_ROOT, "services/api/.venv/bin/python");
  if (!existsSync(venvPython)) return;

  for (const m of REQUIRED_VENV_MODULES) {
    if (exitsZero(`"${venvPython}" -c "import ${m.module}"`)) continue;
    fail(
      `Python module '${m.module}' is not installed in services/api/.venv`,
      m.hint,
    );
  }
}

// ----- Network -----

// Try to bind on a single host; resolves to true if EADDRINUSE.
function isPortBoundOn(port, host) {
  return new Promise((res) => {
    const server = createServer();
    server.once("error", (err) => res(err.code === "EADDRINUSE"));
    server.once("listening", () => server.close(() => res(false)));
    server.listen(port, host);
  });
}

// We probe the wildcard interfaces (0.0.0.0 and ::) because that's what
// `next dev` and `uvicorn` actually try to bind to. Probing only the
// loopbacks misses the common case (on macOS) where a process bound to
// `::` doesn't conflict with a `127.0.0.1` probe but DOES conflict with
// `pnpm dev`'s own wildcard bind. If either wildcard is taken, the
// port is effectively unusable for the dev server.
async function checkPort({ port, name }) {
  const [v4, v6] = await Promise.all([
    isPortBoundOn(port, "0.0.0.0"),
    isPortBoundOn(port, "::"),
  ]);
  if (v4 || v6) {
    warn(
      `Port ${port} (${name}) is already in use`,
      `ok — \`pnpm dev\` will pick the next free port automatically. ` +
        `To inspect what's on it: \`lsof -nP -iTCP:${port} -sTCP:LISTEN\`.`,
    );
  }
}

// ----- Run -----

async function main() {
  checkNode();
  checkPnpm();
  checkPython();
  checkVenv();
  checkEnv();
  checkTools();
  checkVenvPythonModules();
  await Promise.all(PORTS_TO_CHECK.map(checkPort));

  if (failures.length === 0 && warnings.length === 0) {
    console.log("✓ doctor: environment looks good");
    return;
  }

  if (warnings.length > 0) {
    console.error("\n⚠  Warnings:");
    for (const { msg, fix } of warnings) {
      console.error(`  - ${msg}`);
      console.error(`    fix: ${fix}`);
    }
  }

  if (failures.length > 0) {
    console.error("\n✗ Errors:");
    for (const { msg, fix } of failures) {
      console.error(`  - ${msg}`);
      console.error(`    fix: ${fix}`);
    }
    console.error("");
    process.exit(1);
  }

  // Warnings only — non-fatal so `pnpm dev` can still proceed if the
  // user genuinely wants to (e.g. running a second instance).
  console.error("\nProceeding despite warnings.\n");
}

main();
