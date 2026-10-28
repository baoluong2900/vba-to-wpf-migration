import { NextResponse } from 'next/server';
import { layer2Client, promisifyGrpcCall } from '../../../grpcClient';
import fs from 'fs';
import { CONFIG_PATH } from '../../../../../lib/paths';

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
    const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
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
        { id: 'qwen3-coder-480b-a35b-instruct', label: 'Qwen3 Coder 480B Instruct', provider: 'alibaba' },
        { id: 'qwen3-235b-a22b-instruct-2507', label: 'Qwen3 235B Instruct (2507)', provider: 'alibaba' },
        { id: 'qwen-plus-2025-07-28', label: 'Qwen Plus 2025-07-28', provider: 'alibaba' },
        { id: 'qwen3-vl-235b-a22b-thinking', label: 'Qwen3 VL 235B Thinking', provider: 'alibaba' },
        { id: 'qwen-max', label: 'Qwen Max', provider: 'alibaba' },
        { id: 'qvq-max-2025-03-25', label: 'QVQ Max 2025-03-25', provider: 'alibaba' },
      ],
    });
  }
}
