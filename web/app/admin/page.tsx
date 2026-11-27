import Placeholder from "@/components/Placeholder";

export default function AdminPage() {
  return (
    <Placeholder
      title="운영자 화면"
      screen="SCR-06"
      apis={["GET /api/admin/status (M-01, 아직 501)", "POST /api/admin/reprocess (M-03, 아직 501)"]}
      todo={["관리자 로그인 확인(A-01 완료 후)", "출처별 수집 시각·실패 건수", "실패 건 재처리 버튼"]}
    />
  );
}
