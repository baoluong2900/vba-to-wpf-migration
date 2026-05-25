import { NextResponse } from 'next/server';
import { layer1Client, promisifyGrpcCall } from '../grpcClient';

export async function GET() {
  let attempts = 0;
  const maxAttempts = 3;

  while (attempts < maxAttempts) {
    attempts++;
    try {
      console.log(`[api/items] Fetch attempt ${attempts} to gRPC ListAllItems`);
      const response = await promisifyGrpcCall<any, any>(
        layer1Client.ListAllItems.bind(layer1Client),
        {}
      );

      if (!response.success) {
        return NextResponse.json({ success: false, error: response.error }, { status: 500 });
      }

      const result = response.result.map((item: string) => JSON.parse(item));
      return NextResponse.json({ success: true, result });

    } catch (error: any) {
      console.error(`[api/items] Attempt ${attempts} failed:`, error.message);
      if (attempts >= maxAttempts) {
        return NextResponse.json({ 
          success: false, 
          error: `Backend gRPC Server unavailable after ${maxAttempts} attempts. Please ensure start.py is running.` 
        }, { status: 503 });
      }
      // Wait 1s before next attempt
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}
