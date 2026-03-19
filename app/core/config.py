from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Clair Backend"
    mysql_url: str = "mysql+pymysql://user:password@localhost:3306/clair"
