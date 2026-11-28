// /api/chat 호출과 이벤트 묶기. 홈 대화 패널과 공고 상세(판정·질문)가 같이 쓴다.
import { readSse, type AgentEvent } from "@/lib/sse";
import { errorMessage, s } from "@/lib/labels";

export type AgentMode = "auto" | "eligibility" | "notice_qa" | "definition";

export type ChatProfile = {
  region: string | null;
  business_age_years: number | null;
  pre_founder: boolean | null;
  founder_age: number | null;
  applicant_type?: string[] | null;
};

export type ChatBody = {
  question: string;
  profile: ChatProfile;
  notice_id?: string | null;
  top?: number;
  include_closed?: boolean;
  ask_count?: number;
  agent?: AgentMode;
};

/** 스트림을 읽어 이벤트마다 onEvent를 부른다. 실패하면 사용자에게 보일 문구를 돌려준다. */
export async function streamChat(body: ChatBody, onEvent: (e: AgentEvent) => void, signal: AbortSignal): Promise<string> {
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok) return errorMessage(await res.json().catch(() => null), res.status);
    for await (const e of readSse(res)) onEvent(e);
    return "";
  } catch (e) {
    if ((e as Error).name === "AbortError") return "중지했습니다. 이미 받은 판정과 근거는 그대로 둡니다.";
    return "연결이 끊겼습니다. 이미 받은 판정은 유지합니다. 잠시 뒤 다시 시도해 주세요.";
  }
}

export type NoticeView = {
  id: string;
  verdict?: AgentEvent;
  requirements: AgentEvent[];
  paths: AgentEvent[];
  definitions: AgentEvent[];
};
export type Chunk = {
  chunk_id: string;
  notice_id?: string;
  title?: string;
  section?: string;
  source?: string;
  detail_url?: string;
  score?: number;
  text?: string;
  agent: string;
  n: number; // 화면 인용 번호(1부터)
};
export type Segment = { agent: string; template: boolean; text: string };
export type AgentStep = { step: number; name: string; started: boolean; ended: boolean; outcome?: string };
export type TurnView = {
  route?: AgentEvent;
  steps: AgentStep[];
  retrievals: AgentEvent[];
  chunks: Chunk[];
  cited: Set<string>;
  notices: NoticeView[];
  definitions: AgentEvent[]; // 공고에 붙지 않은 정의(정의 에이전트)
  segments: Segment[];
  banners: AgentEvent[];
  ask?: AgentEvent;
  done?: AgentEvent;
  usage?: AgentEvent;
};

export function buildTurn(events: AgentEvent[]): TurnView {
  const notices = new Map<string, NoticeView>();
  const get = (id: string) => {
    if (!notices.has(id)) notices.set(id, { id, requirements: [], paths: [], definitions: [] });
    return notices.get(id)!;
  };
  const steps = new Map<string, AgentStep>();
  const retrievals: AgentEvent[] = [];
  const chunks = new Map<string, Chunk>();
  const cited = new Set<string>();
  const looseDefs: AgentEvent[] = [];
  const segments: Segment[] = [];
  const banners: AgentEvent[] = [];
  const view: Partial<TurnView> = {};

  for (const e of events) {
    const nid = s(e.notice_id);
    switch (e.type) {
      case "route":
        view.route = e;
        break;
      case "agent": {
        const key = `${s(e.step)}:${s(e.name)}`;
        const st = steps.get(key) ?? { step: Number(e.step) || steps.size + 1, name: s(e.name), started: false, ended: false };
        if (e.status === "start") st.started = true;
        if (e.status === "end") {
          st.ended = true;
          st.outcome = e.outcome == null ? undefined : s(e.outcome);
        }
        steps.set(key, st);
        break;
      }
      case "retrieval":
        retrievals.push(e);
        for (const c of (e.chunks as Omit<Chunk, "agent" | "n">[] | undefined) ?? []) {
          if (c?.chunk_id && !chunks.has(c.chunk_id)) chunks.set(c.chunk_id, { ...c, agent: s(e.agent), n: chunks.size + 1 });
        }
        break;
      case "citation":
        for (const id of (e.chunk_ids as string[] | undefined) ?? []) cited.add(id);
        break;
      case "verdict":
        get(nid).verdict = e;
        break;
      case "requirement":
        get(nid).requirements.push(e);
        break;
      case "path":
        get(nid).paths.push(e);
        break;
      case "definition":
        if (nid && (e.text == null || notices.has(nid))) get(nid).definitions.push(e);
        else looseDefs.push(e);
        break;
      case "token": {
        const agent = s(e.agent);
        const template = e.source === "template";
        const last = segments[segments.length - 1];
        if (last && last.agent === agent && last.template === template) last.text += s(e.text);
        else segments.push({ agent, template, text: s(e.text) });
        break;
      }
      case "banner":
      case "error":
        banners.push(e);
        break;
      case "ask":
        view.ask = e;
        break;
      case "usage":
        view.usage = e;
        break;
      case "done":
        view.done = e;
        break;
    }
  }
  // 판정 없이 정의만 붙은 공고 묶음은 따로 보이는 정의 카드로 돌린다
  const shown: NoticeView[] = [];
  for (const n of notices.values()) {
    if (n.verdict || n.requirements.length) shown.push(n);
    else looseDefs.push(...n.definitions);
  }
  return {
    ...view,
    steps: [...steps.values()].sort((a, b) => a.step - b.step),
    retrievals,
    chunks: [...chunks.values()],
    cited,
    notices: shown,
    definitions: looseDefs,
    segments,
    banners,
  };
}

/** 답변 문장의 [chunk_id] 표시를 찾는다. chunk_id는 `KS_123#apply_method:0`처럼 #을 품는다. */
export const CITE_RE = /\[([^\[\]\s]+#[^\[\]\s]+)\]/g;
