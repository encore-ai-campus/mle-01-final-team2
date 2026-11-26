// fetch 응답 본문(text/event-stream)을 이벤트 단위로 읽는다. EventSource는 POST를 못 하므로 직접 파싱한다.
export type AgentEvent = { type: string; [k: string]: unknown };

export async function* readSse(res: Response): AsyncGenerator<AgentEvent> {
  if (!res.body) return;
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value.replace(/\r\n/g, "\n");
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const data = block
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data) as AgentEvent;
    }
  }
}
