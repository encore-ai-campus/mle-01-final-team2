# 저장소 루트에서 빌드: docker build -f api/Dockerfile -t jiwongak-api .
# 실행 대상: AWS CPU 서버(팀 결정). 같은 이미지를 로컬 PC에서도 돌릴 수 있다(Plan B).
# 아직 빌드·배포하지 않았다. 판정 데이터(data/cleaned)를 이미지에 넣을지, Neo4j·Supabase에서 읽을지는 미정이다.
# 비밀 값은 이미지에 넣지 않고 실행할 때 환경변수로 준다: docker run --env-file .env -p 8000:8000 jiwongak-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY api/ api/
COPY tools/graphrag/ tools/graphrag/

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
