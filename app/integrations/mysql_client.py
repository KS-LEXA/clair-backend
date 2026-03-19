class MySQLClient:
    """MySQL 접근 계층을 위한 자리표시자 클래스."""

    def __init__(self, url: str) -> None:
        self.url = url
