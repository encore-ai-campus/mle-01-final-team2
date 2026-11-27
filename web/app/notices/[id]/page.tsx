import Placeholder from "@/components/Placeholder";

export default async function NoticeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Placeholder
      title={`공고 상세: ${decodeURIComponent(id)}`}
      screen="SCR-02, SCR-02-1, SCR-02-2"
      apis={["GET /api/notices/{id} (N-02, 아직 501)", "GET /api/eligibility/{id} (E-02, 아직 501)", "GET /api/graph/path (있음)"]}
      todo={["원문·첨부 상태 표시", "조건별 검증표(필수/참고, 사유, 근거 문장)", "추론 경로 그림"]}
    />
  );
}
