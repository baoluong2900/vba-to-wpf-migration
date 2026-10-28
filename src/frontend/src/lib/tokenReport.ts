import fs from 'fs';
import path from 'path';
import { LAYER5_DIR } from './paths';

export const LAYER5_TOKEN_REPORT_JSON = path.join(LAYER5_DIR, 'logs', 'token_report.json');
export const LAYER5_TOKEN_REPORT_XLSX = path.join(LAYER5_DIR, 'logs', 'token_report.xlsx');

/** Latest Layer 5 token session written by llm/token_tracker.py, or null if none yet. */
export function readLayer5TokenReport(): unknown {
  try {
    if (!fs.existsSync(LAYER5_TOKEN_REPORT_JSON)) return null;
    return JSON.parse(fs.readFileSync(LAYER5_TOKEN_REPORT_JSON, 'utf-8'));
  } catch (err) {
    console.error('[layer5] Failed to read token_report.json:', err);
    return null;
  }
}
