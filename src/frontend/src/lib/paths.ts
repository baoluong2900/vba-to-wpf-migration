import fs from 'fs';
import path from 'path';

const ROOT_MARKER = path.join('src', 'backend', 'protos', 'workflow.proto');

/**
 * The workflow root holds config.json and src/. VBA_BRAIN_ROOT overrides it; otherwise walk up
 * from the working directory (normally src/frontend) until the backend proto is found.
 */
export function resolveWorkflowRoot(
  env: Record<string, string | undefined> = process.env,
  cwd: string = process.cwd(),
  exists: (file: string) => boolean = fs.existsSync,
): string {
  const override = env.VBA_BRAIN_ROOT?.trim();
  if (override) return path.resolve(override);

  let dir = path.resolve(cwd);
  for (let depth = 0; depth < 4; depth++) {
    if (exists(path.join(dir, ROOT_MARKER))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(cwd, '..', '..');
}

export const WORKFLOW_ROOT = resolveWorkflowRoot();
export const CONFIG_PATH = path.join(WORKFLOW_ROOT, 'config.json');
export const BACKEND_DIR = path.join(WORKFLOW_ROOT, 'src', 'backend');
export const PROTO_PATH = path.join(BACKEND_DIR, 'protos', 'workflow.proto');
export const BACKEND_LOGS_DIR = path.join(BACKEND_DIR, 'logs');
export const LAYER1_DIR = path.join(BACKEND_DIR, 'workflow', 'layer1');
export const LAYER5_DIR = path.join(BACKEND_DIR, 'workflow', 'layer5');
export const GRAPHVIEW_DIR = path.join(LAYER5_DIR, 'agents', 'graphview');
export const WPF_DIR = path.join(WORKFLOW_ROOT, 'src', 'wpf');
export const WPF_GRAPH_REPORTS_DIR = path.join(WORKFLOW_ROOT, 'src', 'frontend', 'reports', 'wpf-graph');
