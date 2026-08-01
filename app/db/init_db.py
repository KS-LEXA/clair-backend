from app.db.session import engine, Base
from app.models import user, contract, analysis, chat, social_account, notification, password_reset, contract_share, email_verification, deleted_contract  # noqa: F401


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ 데이터베이스 테이블 초기화 완료")
