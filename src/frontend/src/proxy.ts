import { NextResponse, type NextRequest } from 'next/server';
import { checkSameOrigin } from './lib/originCheck';

/** Blocks cross-site requests to /api/**: several routes spawn Python or dotnet, and one GET makes paid LLM calls. */
export function proxy(request: NextRequest) {
  const verdict = checkSameOrigin({
    method: request.method,
    secFetchSite: request.headers.get('sec-fetch-site'),
    origin: request.headers.get('origin'),
    host: request.headers.get('host'),
  });
  if (!verdict.ok) {
    return NextResponse.json(
      { success: false, error: `Cross-site request blocked (${verdict.reason})` },
      { status: 403 },
    );
  }
  return NextResponse.next();
}

export const config = {
  matcher: '/api/:path*',
};
