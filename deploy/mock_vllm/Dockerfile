# vLLM 대역 서버(OpenAI 호환). 진짜 모델이 아니다. 저장소 루트에서 빌드한다:
#   docker build -f deploy/mock_vllm/Dockerfile -t jiwongak-mock-vllm .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115,<1" "uvicorn>=0.32,<1"
COPY deploy/__init__.py deploy/__init__.py
COPY deploy/mock_vllm/ deploy/mock_vllm/

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)"
CMD ["uvicorn", "deploy.mock_vllm.app:app", "--host", "0.0.0.0", "--port", "8001"]
