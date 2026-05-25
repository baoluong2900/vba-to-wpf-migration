import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'path';

// Next.js runs from src/frontend, so the proto is located at src/backend/protos/workflow.proto
const PROTO_PATH = path.join(process.cwd(), '../backend/protos/workflow.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition) as any;
const apiV1 = protoDescriptor.api.v1;

const grpcAddress = process.env.GRPC_SERVER_ADDRESS || 'localhost:50051';

export const layer1Client = new apiV1.Layer1Service(
  grpcAddress,
  grpc.credentials.createInsecure()
);

export const layer2Client = new apiV1.Layer2Service(
  grpcAddress,
  grpc.credentials.createInsecure()
);

export const layer3Client = new apiV1.Layer3Service(
  grpcAddress,
  grpc.credentials.createInsecure()
);

export const layer4Client = new apiV1.Layer4Service(
  grpcAddress,
  grpc.credentials.createInsecure()
);

export function promisifyGrpcCall<TRequest, TResponse>(
  clientMethod: (req: TRequest, callback: (err: any, res: TResponse) => void) => void,
  request: TRequest
): Promise<TResponse> {
  return new Promise((resolve, reject) => {
    clientMethod(request, (err, response) => {
      if (err) {
        reject(err);
      } else {
        resolve(response);
      }
    });
  });
}
