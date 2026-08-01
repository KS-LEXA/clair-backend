# clair-backend — FastAPI REST API
FROM python:3.11-slim

# WeasyPrint(PDF 리포트)가 pango/cairo를 dlopen 하므로 런타임 라이브러리가 필요하다.
# fonts-nanum은 필수: 없으면 한글 PDF가 전부 두부(□)로 렌더링된다.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi8 \
        shared-mime-info \
        fonts-nanum \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 업로드된 계약서 원본이 쌓이는 경로. 영속 볼륨을 마운트해야 재시작 후에도
# 기존 계약서를 열 수 있다. 프로필 이미지도 이 아래에 저장된다.
ENV UPLOAD_DIR=/data/uploads
RUN mkdir -p /data/uploads
VOLUME ["/data"]

EXPOSE 8000

# 스키마는 startup의 create_all이 아니라 Alembic을 정본으로 삼는다.
# 컨테이너 기동 시 마이그레이션을 먼저 적용한 뒤 서버를 띄운다.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
