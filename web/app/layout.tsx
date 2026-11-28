import type { Metadata } from "next";
import Link from "next/link";

import AuthNav from "@/components/AuthNav";
import { DISCLAIMER } from "@/lib/labels";
import "./globals.css";

export const metadata: Metadata = { title: "지원각", description: "정부 지원사업 신청 자격 확인(참고용)" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="site-head">
          <nav aria-label="주 메뉴">
            <Link href="/" className="brand">
              지원각
            </Link>
            <Link href="/">홈</Link>
            <Link href="/notices">공고</Link>
            <Link href="/admin">운영</Link>
            <AuthNav />
          </nav>
        </header>
        {children}
        <footer className="site-foot" role="contentinfo">
          ※ {DISCLAIMER} 선정을 보장하지 않습니다. 교육용 프로젝트(팀 근거 it).
        </footer>
      </body>
    </html>
  );
}
