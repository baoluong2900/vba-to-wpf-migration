import fs from 'fs';
import path from 'path';

const INSTALL_CANDIDATES = [
  '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
  '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3',
  '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3',
  '/opt/homebrew/bin/python3',
  '/usr/local/bin/python3',
];

export type PythonLookup = {
  env?: Record<string, string | undefined>;
  platform?: string;
  isExecutable?: (file: string) => boolean;
};

function isExecutableFile(file: string): boolean {
  try {
    if (!fs.statSync(file).isFile()) return false;
    fs.accessSync(file, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/** PYTHON_BIN, then python3 / python on PATH (python3 first), then common install locations. */
export function resolvePython({
  env = process.env,
  platform = process.platform,
  isExecutable = isExecutableFile,
}: PythonLookup = {}): string {
  const override = env.PYTHON_BIN?.trim();
  if (override) return override;

  const win = platform === 'win32';
  const p = win ? path.win32 : path.posix;
  const pathKey = Object.keys(env).find((key) => key.toUpperCase() === 'PATH');
  const dirs = (pathKey ? env[pathKey] ?? '' : '').split(win ? ';' : ':').filter(Boolean);

  for (const name of ['python3', 'python']) {
    for (const dir of dirs) {
      // WindowsApps holds Microsoft Store alias stubs, not interpreters.
      if (win && /[\\/]WindowsApps[\\/]?$/i.test(dir)) continue;
      const file = p.join(dir, win ? `${name}.exe` : name);
      if (isExecutable(file)) return file;
    }
  }
  if (!win) {
    const installed = INSTALL_CANDIDATES.find((file) => isExecutable(file));
    if (installed) return installed;
  }
  return win ? 'python' : 'python3';
}

let resolved: string | undefined;

/** Resolved once per process; every route that spawns Python uses this. */
export function pythonExecutable(): string {
  if (resolved === undefined) resolved = resolvePython();
  return resolved;
}
