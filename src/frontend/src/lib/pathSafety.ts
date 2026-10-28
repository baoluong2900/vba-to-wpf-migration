const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;

/**
 * True when `name` (an Access form/report/macro/module name) can be used as a single path
 * segment and a positional CLI argument: no separators, NUL/control characters, "." / "..",
 * Windows drive prefix ("C:") or leading "-". Japanese and other non-ASCII names are fine.
 */
export function isSafeName(name: unknown): name is string {
  if (typeof name !== 'string' || name.length === 0 || name.length > 255) return false;
  if (name === '.' || name.includes('..')) return false;
  if (/[\\/]/.test(name) || CONTROL_CHARS.test(name)) return false;
  if (/^[A-Za-z]:/.test(name) || name.startsWith('-')) return false;
  return true;
}

/** A value passed as one CLI option argument (e.g. a model id). */
export function isSafeCliValue(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= 200 &&
    !value.startsWith('-') &&
    !CONTROL_CHARS.test(value)
  );
}
