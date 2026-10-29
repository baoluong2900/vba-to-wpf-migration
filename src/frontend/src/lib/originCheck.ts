const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export type OriginCheckInput = {
  method: string;
  secFetchSite?: string | null;
  origin?: string | null;
  host?: string | null;
};

export type OriginCheckResult = { ok: boolean; reason?: string };

/**
 * Same-origin check for /api requests. Sec-Fetch-Site wins when the browser sends it, for every
 * method ("same-origin" or "none" pass): GET is not harmless here, since
 * GET /api/v1/layer2/models/health makes paid LLM calls and an <img> on any page could trigger it.
 * Without Sec-Fetch-Site, state-changing requests need an Origin host equal to Host. Requests with
 * neither header come from non-browser clients (curl, scripts) and cannot be forged cross-site.
 */
export function checkSameOrigin({ method, secFetchSite, origin, host }: OriginCheckInput): OriginCheckResult {
  if (secFetchSite) {
    const site = secFetchSite.toLowerCase();
    return site === 'same-origin' || site === 'none'
      ? { ok: true }
      : { ok: false, reason: `Sec-Fetch-Site: ${secFetchSite}` };
  }

  if (SAFE_METHODS.has(method.toUpperCase()) || !origin) return { ok: true };

  let originHost: string;
  try {
    originHost = new URL(origin).host;
  } catch {
    return { ok: false, reason: `invalid Origin "${origin}"` };
  }
  if (host && originHost.toLowerCase() === host.toLowerCase()) return { ok: true };
  return { ok: false, reason: `Origin ${origin} does not match Host ${host ?? '(missing)'}` };
}
