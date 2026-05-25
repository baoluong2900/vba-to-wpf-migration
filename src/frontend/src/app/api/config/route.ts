import { NextResponse } from 'next/server';
import { layer2Client, promisifyGrpcCall } from '../grpcClient';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer2Client.GetConfig.bind(layer2Client),
      {}
    );

    if (response.success) {
      const models = JSON.parse(response.models_json);
      return NextResponse.json({ success: true, models });
    }
  } catch (error) {
    // Fallback if gRPC is down
  }

  // Fallback: đọc config.json trực tiếp
  try {
    const configPath = path.resolve(process.cwd(), '../config.json');
    const raw = fs.readFileSync(configPath, 'utf-8');
    const cfg = JSON.parse(raw);

    const providers = cfg.llm_providers || {};
    const models: { id: string; label: string; provider: string }[] = [];
    for (const [providerName, providerCfg] of Object.entries(providers) as [string, any][]) {
      for (const m of (providerCfg.models || [])) {
        models.push({ id: m, label: m, provider: providerName });
      }
    }
    return NextResponse.json({ success: true, models });
  } catch (err: any) {
    return NextResponse.json({
      success: false,
      error: err.message,
      models: [
        { id: 'deepseek-v4-pro', label: 'DeepSeek v4 Pro', provider: 'deepseek' },
        { id: 'deepseek-v4-flash', label: 'DeepSeek v4 Flash', provider: 'deepseek' },
      ],
    });
  }
}
