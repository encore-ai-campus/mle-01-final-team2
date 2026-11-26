import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "지원각", description: "정부 지원사업 신청 자격 확인(참고용)" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
