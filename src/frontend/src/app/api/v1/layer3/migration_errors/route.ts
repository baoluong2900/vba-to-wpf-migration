import { NextResponse } from 'next/server';
import { getDb } from '../../../graph/graphBuilder';

export async function GET() {
  try {
    const db = await getDb();
    const col = db.collection('queries_v2');
    const docs = await col.find({ conversion_status: 'error' }).toArray();
    const errors = docs.map(doc => ({
      query_name: doc.name,
      timestamp: doc.updated_at || doc.created_at || new Date().toISOString(),
      error_message: doc.notes || 'Unknown conversion error',
      source_operation: 'AI SQL Translation',
      sql: doc.sql || ''
    }));
    return NextResponse.json(errors);
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
