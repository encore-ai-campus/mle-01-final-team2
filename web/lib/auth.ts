"use client";
// 로그인(A-01). Supabase Auth 세션은 브라우저에 두고, 우리 API를 부를 때 액세스 토큰을 Authorization 헤더로 붙인다.
// Supabase 주소·공개 키는 API(GET /api/auth/config)에서 받는다. 비밀 키는 브라우저로 오지 않는다.
// 역할(user/admin)은 서버가 허용 목록으로 정한다(GET /api/me). 화면의 역할 표시는 안내일 뿐 권한이 아니다.
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { useEffect, useState } from "react";

type AuthConfig = { enabled: boolean; url: string | null; publishable_key: string | null; providers: string[] };
export type Me = { user_id: string; role: "user" | "admin"; dev: boolean; email: string | null };

let clientPromise: Promise<SupabaseClient | null> | null = null;
let providerList: string[] = [];

/** Supabase에서 켜 둔 로그인 방법(email, google 등). supabase()를 부른 뒤에 채워진다. */
export const loginProviders = () => providerList;

export function supabase(): Promise<SupabaseClient | null> {
  if (!clientPromise) {
    clientPromise = fetch("/api/auth/config")
      .then((r) => (r.ok ? (r.json() as Promise<AuthConfig>) : null))
      .then((c) => {
        providerList = c?.providers ?? [];
        return c;
      })
      .then((c) => (c?.enabled && c.url && c.publishable_key ? createClient(c.url, c.publishable_key, { auth: { flowType: "implicit", detectSessionInUrl: true, persistSession: true } }) : null))
      .catch(() => {
        clientPromise = null; // 다음 호출에서 다시 시도
        return null;
      });
  }
  return clientPromise;
}

export async function accessToken(): Promise<string | null> {
  const sb = await supabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession(); // 만료가 가까우면 supabase-js가 갱신한다
  return data.session?.access_token ?? null;
}

/** 우리 API(/api/...)를 부를 때 쓰는 fetch. 로그인했으면 토큰을 붙인다. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken();
  if (!token) return fetch(input, init);
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

/** 현재 세션과 서버가 본 사용자(역할). 로그인·로그아웃하면 다시 읽는다. */
export function useAuth(): { ready: boolean; enabled: boolean; session: Session | null; me: Me | null } {
  const [state, setState] = useState<{ ready: boolean; enabled: boolean; session: Session | null; me: Me | null }>({ ready: false, enabled: false, session: null, me: null });
  useEffect(() => {
    let alive = true;
    let unsub: (() => void) | undefined;
    const load = async (session: Session | null, enabled: boolean) => {
      const headers: Record<string, string> = session ? { authorization: `Bearer ${session.access_token}` } : {};
      const me = await fetch("/api/me", { headers })
        .then((r) => (r.ok ? (r.json() as Promise<Me>) : null))
        .catch(() => null);
      if (alive) setState({ ready: true, enabled, session, me });
    };
    supabase().then(async (sb) => {
      if (!sb) return load(null, false);
      const { data } = await sb.auth.getSession();
      await load(data.session, true);
      const { data: sub } = sb.auth.onAuthStateChange((event, session) => {
        if (event === "SIGNED_IN" || event === "SIGNED_OUT" || event === "USER_UPDATED") load(session, true);
      });
      unsub = () => sub.subscription.unsubscribe();
    });
    return () => {
      alive = false;
      unsub?.();
    };
  }, []);
  return state;
}

export async function signOut(): Promise<void> {
  const sb = await supabase();
  await sb?.auth.signOut();
}
