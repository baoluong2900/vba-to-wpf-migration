import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import { PROTO_PATH } from '../../lib/paths';
import { bearerAuthInterceptor } from '../../lib/grpcAuth';

type ServiceName = 'Layer1Service' | 'Layer2Service' | 'Layer3Service' | 'Layer4Service';

let apiV1: any = null;
const clients = new Map<ServiceName, any>();

function getClient(service: ServiceName): any {
  let client = clients.get(service);
  if (!client) {
    if (!apiV1) {
      const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true,
      });
      apiV1 = (grpc.loadPackageDefinition(packageDefinition) as any).api.v1;
    }
    const token = process.env.GRPC_AUTH_TOKEN;
    client = new apiV1[service](
      process.env.GRPC_SERVER_ADDRESS || 'localhost:50051',
      grpc.credentials.createInsecure(),
      token ? { interceptors: [bearerAuthInterceptor(token)] } : {},
    );
    clients.set(service, client);
  }
  return client;
}

/**
 * Proto loading and channel creation happen on first use, inside the calling route's try/catch,
 * so a bad proto path becomes a JSON error instead of a module-evaluation crash.
 */
function lazyClient(service: ServiceName): any {
  return new Proxy(
    {},
    {
      get(_target, prop) {
        const client = getClient(service);
        const value = client[prop];
        if (typeof value === 'function') return value.bind(client);
        if (value === undefined && typeof prop === 'string' && /^[A-Z]/.test(prop)) {
          throw new Error(`${service} has no RPC named ${prop}`);
        }
        return value;
      },
    },
  );
}

export const layer1Client = lazyClient('Layer1Service');
export const layer2Client = lazyClient('Layer2Service');
// The proto names are swapped: Layer4Service is SQL migration (UI layer 3), Layer3Service is Excel (UI layer 4).
export const layer3Client = lazyClient('Layer4Service');
export const layer4Client = lazyClient('Layer3Service');

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
