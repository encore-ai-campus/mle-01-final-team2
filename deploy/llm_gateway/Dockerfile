# 로컬 LLM 게이트웨이(vLLM 호환 API → 외부 OpenAI 모델). 저장소 루트에서 빌드한다:
#   docker build -f deploy/llm_gateway/Dockerfile -t jiwongak-llm-gateway .
# 키는 이미지에 넣지 않고 실행할 때 환경변수로 준다(docker compose가 저장소 루트 .env를 붙인다).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115,<1" "uvicorn>=0.32,<1" "httpx>=0.27,<1"
COPY deploy/__init__.py deploy/__init__.py
COPY deploy/llm_gateway/ deploy/llm_gateway/

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)"
CMD ["uvicorn", "deploy.llm_gateway.app:app", "--host", "0.0.0.0", "--port", "8001"]
