// SCR-02 공고 상세. ?tab=source|verify|reasoning 으로 원문(SCR-02)·조건별 검증(SCR-02-1)·추론 과정(SCR-02-2) 탭을 고른다.
// 내용은 클라이언트 컴포넌트가 /api/notices/{id}·/api/eligibility/{id}·/api/graph/path·/api/chat으로 채운다.
import NoticeDetail, { type DetailTab } from "@/components/NoticeDetail";

const TABS: DetailTab[] = ["source", "verify", "reasoning"];

export default async function NoticeDetailPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ tab?: string }> }) {
  const { id } = await params;
  const { tab } = await searchParams;
  const initial = TABS.includes(tab as DetailTab) ? (tab as DetailTab) : "source";
  return <NoticeDetail id={decodeURIComponent(id)} initialTab={initial} />;
}
