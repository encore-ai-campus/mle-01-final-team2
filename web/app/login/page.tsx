"use client";
// 로그인(SCR-00, A-01). Supabase Auth: Google(대시보드에서 켜야 함) 또는 이메일 로그인 링크.
// 로그인 링크를 누르면 이 화면으로 돌아오고, supabase-js가 주소의 토큰을 읽어 세션을 만든다.
import Link from "next/link";
import { useState } from "react";

import { loginProviders, signOut, supabase, useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { ready, enabled, session, me } = useAuth();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const back = typeof window === "undefined" ? "" : `${window.location.origin}/login`;

  const google = async () => {
    const sb = await supabase();
    if (!sb) return;
    const { error } = await sb.auth.signInWithOAuth({ provider: "google", options: { redirectTo: back } });
    if (error) setMsg(error.message.includes("not enabled") ? "Google 로그인이 아직 켜져 있지 않습니다. 이메일 로그인을 쓰세요." : error.message);
  };

  const magic = async (e: React.FormEvent) => {
    e.preventDefault();
    const sb = await supabase();
    if (!sb || !email.trim()) return;
    setBusy(true);
    const { error } = await sb.auth.signInWithOtp({ email: email.trim(), options: { emailRedirectTo: back } });
    setBusy(false);
    setMsg(error ? error.message : "로그인 링크를 보냈습니다. 메일의 링크를 이 브라우저에서 여세요.");
  };

  return (
    <main>
      <h1>로그인</h1>
      {!ready && <div className="muted">확인 중…</div>}
      {ready && !enabled && (
        <div className="banner">로그인 설정이 없습니다(API의 SUPABASE_URL·SUPABASE_KEY). 로컬 개발에서는 로그인 없이 개발용 사용자로 동작합니다.</div>
      )}
      {ready && enabled && session && (
        <section className="panel">
          <div>
            <strong>{me?.email ?? session.user.email}</strong> 로 로그인했습니다. 역할: {me ? (me.role === "admin" ? "관리자" : "사용자") : "확인 실패"}
          </div>
          {me?.role === "admin" && (
            <div className="row">
              <Link href="/admin/reviews">요건 검수 큐</Link>
              <Link href="/admin">시스템 상태</Link>
            </div>
          )}
          <div className="row">
            <button type="button" onClick={() => signOut()}>
              로그아웃
            </button>
          </div>
        </section>
      )}
      {ready && enabled && !session && (
        <section className="panel">
          {loginProviders().includes("google") ? (
            <button type="button" className="primary" onClick={google}>
              Google로 로그인
            </button>
          ) : (
            <div className="muted">Google 로그인은 아직 꺼져 있습니다(Supabase 대시보드에서 켜야 함). 이메일 로그인 링크를 쓰세요.</div>
          )}
          <form onSubmit={magic} className="row">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="이메일" aria-label="이메일" required />
            <button type="submit" disabled={busy}>
              로그인 링크 받기
            </button>
          </form>
          <div className="muted" style={{ marginTop: 8 }}>
            관리자 권한은 서버의 허용 목록으로 정해집니다. 로그인해도 허용 목록에 없으면 일반 사용자입니다.
          </div>
        </section>
      )}
      {msg && <div className="banner">{msg}</div>}
    </main>
  );
}
