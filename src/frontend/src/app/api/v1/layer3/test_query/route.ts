import { NextRequest, NextResponse } from 'next/server';
import { staticSqlCheck } from '../staticSqlCheck';

// Static check only (see ../staticSqlCheck.ts) — the SQL is never executed.
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    return NextResponse.json(staticSqlCheck(body.target_sql || ''));
  } catch (error: any) {
    return NextResponse.json({ success: false, preview: true, error_message: error.message }, { status: 400 });
  }
}
