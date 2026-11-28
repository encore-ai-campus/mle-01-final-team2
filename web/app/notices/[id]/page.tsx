// SCR-02 공고 상세. 내용은 클라이언트 컴포넌트가 /api/notices/{id}·/api/chat·/api/graph/path로 채운다.
import NoticeDetail from "@/components/NoticeDetail";

export default async function NoticeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <NoticeDetail id={decodeURIComponent(id)} />;
}
