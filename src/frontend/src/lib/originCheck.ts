const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export type OriginCheckInput = {
  method: string;
  secFetchSite?: string | null;
  origin?: string | null;
  host?: string | null;
};

export type OriginCheckResult = { ok: boolean; reason?: string };

/**
 * Same-origin check for state-changing requests. Sec-Fetch-Site wins when present
 * ("same-origin" or "none" pass); otherwise the Origin host must equal Host. Requests with
 * neither header come from non-browser clients (curl, scripts) and cannot be forged cross-site.
 */
export function checkSameOrigin({ method, secFetchSite, origin, host }: OriginCheckInput): OriginCheckResult {
  if (SAFE_METHODS.has(method.toUpperCase())) return { ok: true };

  if (secFetchSite) {
    const site = secFetchSite.toLowerCase();
    return site === 'same-origin' || site === 'none'
      ? { ok: true }
      : { ok: false, reason: `Sec-Fetch-Site: ${secFetchSite}` };
  }

  if (!origin) return { ok: true };

  let originHost: string;
  try {
    originHost = new URL(origin).host;
  } catch {
    return { ok: false, reason: `invalid Origin "${origin}"` };
  }
  if (host && originHost.toLowerCase() === host.toLowerCase()) return { ok: true };
  return { ok: false, reason: `Origin ${origin} does not match Host ${host ?? '(missing)'}` };
}
