# mcp/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from shared.models import Base, User, Class
from typing import Optional

# 修改下面的连接字符串为你的 MySQL 信息
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/campus_assistant?charset=utf8mb4"

engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    # 创建所有表
    Base.metadata.create_all(bind=engine)

def get_user_id_from_external_id(db: Session, external_id: str) -> Optional[int]:
    """通过 external_id 查询用户并返回其自增 id。"""
    user = db.query(User).filter(User.external_id == external_id).first()
    return user.id if user else None

def get_class_id_from_class_code(db: Session, class_code: str) -> Optional[int]:
    """通过 class_code 查询班级并返回其自增 id。"""
    class_obj = db.query(Class).filter(Class.class_code == class_code).first()
    return class_obj.id if class_obj else None
