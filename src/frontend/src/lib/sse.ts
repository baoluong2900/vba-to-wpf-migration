/**
 * Incremental parser for `data: <json>` server-sent events. Text may arrive split anywhere;
 * events are emitted only once their terminating blank line has arrived. Malformed JSON is skipped.
 */
export function createSseParser(onEvent: (data: any) => void) {
  let buffer = '';

  const emit = (block: string) => {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n');
    if (!data) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(data);
    } catch {
      return;
    }
    onEvent(parsed);
  };

  return {
    push(text: string) {
      buffer += text.replace(/\r/g, '');
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';
      blocks.forEach(emit);
    },
    end() {
      if (buffer.trim()) emit(buffer);
      buffer = '';
    },
  };
}

/** Read an SSE response body to the end, decoding UTF-8 across chunk boundaries. */
export async function readSseStream(body: ReadableStream<Uint8Array>, onEvent: (data: any) => void): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser(onEvent);
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.push(decoder.decode());
  parser.end();
}
