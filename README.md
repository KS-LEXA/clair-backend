# CLAIR Backend

AI 기반 계약서 분석 시스템 - FastAPI 백엔드

## 실행 방법

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install bcrypt==4.0.1
cp .env.example .env
# .env에서 DB_PASSWORD, SECRET_KEY 수정
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS clair_db DEFAULT CHARACTER SET utf8mb4;"
uvicorn app.main:app --reload --port 8000
```

API 문서: http://localhost:8000/docs

## 프로젝트 구조

```
app/
├── main.py              # 엔트리포인트
├── api/v1/              # API 엔드포인트
│   ├── auth.py          # 인증 (회원가입, 로그인, 토큰)
│   ├── contracts.py     # 계약서 (업로드, 조회, 삭제)
│   └── chat.py          # 채팅 (세션, 메시지)
├── core/
│   ├── config.py        # 환경변수 설정
│   └── security.py      # JWT, 비밀번호 해싱
├── db/
│   ├── session.py       # DB 연결
│   └── init_db.py       # 테이블 자동 생성
├── models/              # DB 테이블 모델
│   ├── user.py          # users
│   ├── contract.py      # contracts
│   ├── analysis.py      # analysis_results, risk_clauses
│   └── chat.py          # chat_sessions, chat_messages
├── schemas/             # 요청/응답 스키마
├── services/            # 비즈니스 로직
└── integrations/        # AI 연동 (조서현 파트)
```
