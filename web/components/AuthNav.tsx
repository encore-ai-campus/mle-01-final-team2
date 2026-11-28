"use client";
// 머리글의 로그인 상태. 역할 표시는 서버(/api/me)가 정한 값이다.
import Link from "next/link";

import { useAuth } from "@/lib/auth";

export default function AuthNav() {
  const { ready, enabled, session, me } = useAuth();
  if (!ready) return null;
  if (!enabled || !session) {
    return (
      <Link href="/login" className="nav-right">
        {me?.dev ? "개발용 사용자 · 로그인" : "로그인"}
      </Link>
    );
  }
  return (
    <Link href="/login" className="nav-right" title="계정·로그아웃">
      {session.user.email ?? "내 계정"}
      {me?.role === "admin" ? " (관리자)" : ""}
    </Link>
  );
}
