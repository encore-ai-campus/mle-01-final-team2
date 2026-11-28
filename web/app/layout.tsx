import type { Metadata } from "next";
import Link from "next/link";

import AuthNav from "@/components/AuthNav";
import MetaFooter from "@/components/MetaFooter";
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
            <Link href="/">공고 찾기</Link>
            <Link href="/chat">챗봇</Link>
            <Link href="/notices">공고 목록</Link>
            <Link href="/admin">운영</Link>
            <AuthNav />
          </nav>
        </header>
        {children}
        <MetaFooter />
      </body>
    </html>
  );
}
