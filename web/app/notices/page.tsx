import Placeholder from "@/components/Placeholder";

export default function NoticesPage() {
  return (
    <Placeholder
      title="공고 목록"
      screen="SCR-01"
      apis={["GET /api/notices (N-01, 아직 501)", "GET /api/concepts?scheme=region (C-01, 있음)"]}
      todo={["Next 중계 라우트 web/app/api/notices/route.ts 추가(proxyGet 사용)", "검색어·출처·마감 포함 필터와 페이지", "카드에서 /notices/[id]로 이동"]}
    />
  );
}
