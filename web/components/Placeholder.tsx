// 기능 뼈대 화면. 담당자가 실제 화면으로 바꾼다. 무엇을 만들지는 화면설계서 ID와 API 명세 ID로 찾는다.
type Props = { title: string; screen: string; apis: string[]; todo: string[] };

export default function Placeholder({ title, screen, apis, todo }: Props) {
  return (
    <main>
      <h1>{title}</h1>
      <p className="muted">준비 중인 화면입니다. 화면설계서 {screen}</p>
      <h2>쓸 API</h2>
      <ul>{apis.map((a) => <li key={a}><code>{a}</code></li>)}</ul>
      <h2>할 일</h2>
      <ul>{todo.map((t) => <li key={t}>{t}</li>)}</ul>
      <p><a href="/">처음으로</a></p>
    </main>
  );
}
