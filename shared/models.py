# shared/models.py
from sqlalchemy import (
    Table, Column, String, Integer, Date, DateTime, Text, ForeignKey,
    Enum as SAEnum, Boolean, func
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
import enum
from datetime import datetime

Base = declarative_base()

# -------------------------
# 多对多关联表：parents <-> students
# -------------------------
parent_students = Table(
    "parent_students",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("parent_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("student_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow)
)

# 可选：class_students（如果你打算使用它而不是 User.class_id）
class_students = Table(
    "class_students",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("class_id", Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
    Column("student_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow)
)

# ---------- Enums ----------
class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    parent = "parent"
    admin = "admin"

class NoticeType(str, enum.Enum):
    normal = "normal"
    urgent = "urgent"

# ---------- School ----------
class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=True)

    # relationships
    users = relationship("User", back_populates="school", cascade="all, delete", passive_deletes=True)
    class_instances = relationship("ClassInstance", back_populates="school", cascade="all, delete", passive_deletes=True)

# ---------- User ----------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)

    # 业务外部标识（学号/工号等，纯数字串）
    external_id = Column(String(64), unique=True, nullable=True)

    # 学校关联（可空）
    school_id = Column(Integer, ForeignKey("schools.id", name="fk_user_school", ondelete="SET NULL"), nullable=True, index=True)

    # 学生所属班级（legacy：可空，用于兼容旧逻辑）
    class_id = Column(Integer, ForeignKey("classes.id", use_alter=True, name="fk_user_class", ondelete="SET NULL"), nullable=True, index=True)

    # 班主任/管理的班级（legacy：可空）
    managed_class_id = Column(Integer, ForeignKey("classes.id", use_alter=True, name="fk_user_managed_class", ondelete="SET NULL"), nullable=True, index=True)

    # 新模型：当前是否在校、毕业时间
    is_active = Column(Boolean, nullable=False, default=True)
    graduation_date = Column(Date, nullable=True)

    # relationships：back_populates 要对应 Class 中的定义
    # legacy: User.class_ 指向 Class（基于 users.class_id）
    class_ = relationship(
        "Class",
        primaryjoin="Class.id==User.class_id",
        back_populates="students",
        viewonly=False
    )

    managed_class = relationship(
        "Class",
        primaryjoin="Class.id==User.managed_class_id",
        back_populates="managers",
        viewonly=False
    )

    # 学校关系
    school = relationship("School", back_populates="users", foreign_keys=[school_id])

    # 父/子关系（父亲/母亲 -> 学生）
    children = relationship(
        "User",
        secondary=parent_students,
        primaryjoin=id==parent_students.c.parent_id,
        secondaryjoin=id==parent_students.c.student_id,
        backref="parents",
        viewonly=False
    )

    # grades / memos / messages 等关系（已有表的 backrefs）
    grades = relationship("Grade", back_populates="student", foreign_keys="Grade.student_id")
    given_grades = relationship("Grade", back_populates="teacher", foreign_keys="Grade.teacher_id")
    memos = relationship("Memo", back_populates="student", foreign_keys="Memo.student_id")
    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    received_messages = relationship("Message", back_populates="receiver", foreign_keys="Message.receiver_id")

    # enrollments (新的学生在班级实例中的历史)
    enrollments = relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")

# ---------- Class (legacy) ----------
class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    
    # 业务班级编号（纯数字/字符串），如 202501
    class_code = Column(String(32), unique=True, nullable=True, index=True)

    # legacy homeroom teacher FK
    homeroom_teacher_id = Column(Integer, ForeignKey("users.id", use_alter=True, name="fk_class_homeroom_teacher", ondelete="SET NULL"), nullable=True, index=True)
    homeroom_teacher = relationship(
        "User",
        foreign_keys=[homeroom_teacher_id],
        backref="homeroom_of"
    )

    # legacy relationships pointing to users.class_id / users.managed_class_id
    students = relationship(
        "User",
        primaryjoin="Class.id==User.class_id",
        back_populates="class_",
        viewonly=False
    )

    managers = relationship(
        "User",
        primaryjoin="Class.id==User.managed_class_id",
        back_populates="managed_class",
        viewonly=False
    )

    # legacy daily_quotes/open_windows referencing classes (kept for backward compatibility)
    daily_quotes = relationship("DailyQuote", back_populates="class_", foreign_keys="DailyQuote.class_id")
    open_windows = relationship("OpenWindow", back_populates="class_", foreign_keys="OpenWindow.class_id")

# ---------- ClassInstance (new: per-school-year班级实例) ----------
class ClassInstance(Base):
    __tablename__ = "class_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    orig_class_id = Column(Integer, ForeignKey("classes.id", name="fk_ci_orig_class", ondelete="SET NULL"), nullable=True, index=True)
    template_id = Column(Integer, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", name="fk_ci_school", ondelete="SET NULL"), nullable=True, index=True)
    school_year = Column(String(16), nullable=False)
    grade = Column(Integer, nullable=True)   # 1..9
    section = Column(String(32), nullable=True)
    homeroom_teacher_id = Column(Integer, ForeignKey("users.id", name="fk_ci_homeroom_teacher", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relationships
    orig_class = relationship("Class", foreign_keys=[orig_class_id], backref="instances")
    school = relationship("School", back_populates="class_instances", foreign_keys=[school_id])
    homeroom_teacher = relationship("User", foreign_keys=[homeroom_teacher_id], backref="managed_instances")

    # enrollments (students)
    enrollments = relationship("Enrollment", back_populates="class_instance", cascade="all, delete-orphan")

    # daily quotes can optionally reference class_instance (we keep legacy class_id in DailyQuote)
    daily_quotes_instances = relationship("DailyQuote", back_populates="class_instance", foreign_keys="DailyQuote.class_instance_id")

# ---------- Enrollment (new: student history in class instances) ----------
class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_enroll_user", ondelete="CASCADE"), nullable=False, index=True)
    class_instance_id = Column(Integer, ForeignKey("class_instances.id", name="fk_enroll_ci", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(SAEnum("active","graduated","transferred", name="enrollment_status"), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="enrollments", foreign_keys=[user_id])
    class_instance = relationship("ClassInstance", back_populates="enrollments", foreign_keys=[class_instance_id])

# ---------- Message ----------
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    audio_url = Column(String(200), nullable=True)
    priority = Column(SAEnum(NoticeType), default=NoticeType.normal)
    timestamp = Column(DateTime, nullable=False)

    # 通知相关字段（用于 notice / 群发）
    is_notice = Column(Boolean, nullable=False, default=False)
    target_class = Column(String(50), nullable=True)  # legacy: may contain class id or name
    target_role = Column(String(20), nullable=True)

    # 关系：明确哪条 FK 被用作 sender/receiver
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")

# ---------- Grade ----------
class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(50), nullable=False)
    score = Column(Integer, nullable=False)
    semester = Column(String(20), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 新增：指向 class_instances 的可选 FK（兼容迁移）
    class_instance_id = Column(Integer, ForeignKey("class_instances.id", name="fk_grades_ci", ondelete="SET NULL"), nullable=True, index=True)

    student = relationship("User", foreign_keys=[student_id], back_populates="grades")
    teacher = relationship("User", foreign_keys=[teacher_id], back_populates="given_grades")
    class_instance = relationship("ClassInstance", foreign_keys=[class_instance_id])

# ---------- Memo ----------
class Memo(Base):
    __tablename__ = "memos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    remind_date = Column(Date, nullable=False)

    # JSON 列不要在 DDL 里设置默认值（MySQL 限制），设置为 nullable 并由应用端补默认值
    status_json = Column(MySQLJSON, nullable=True)

    student = relationship("User", foreign_keys=[student_id], back_populates="memos")

# ---------- Notice ----------
class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    type = Column(SAEnum(NoticeType), default=NoticeType.normal)
    timestamp = Column(DateTime, nullable=False)

    creator = relationship("User", foreign_keys=[creator_id], backref="created_notices")

# ---------- DailyQuote ----------
class DailyQuote(Base):
    __tablename__ = "daily_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # legacy: class_id 继续保留以兼容旧逻辑（指向 classes.id）
    class_id = Column(Integer, ForeignKey("classes.id", name="fk_dq_class", ondelete="SET NULL"), nullable=True, index=True)

    # 新增：可选指向 class_instances（优先使用）
    class_instance_id = Column(Integer, ForeignKey("class_instances.id", name="fk_dq_ci", ondelete="SET NULL"), nullable=True, index=True)

    date = Column(Date, nullable=True)
    content = Column(Text, nullable=False)
    voice_url = Column(String(255), nullable=True)
    # 为兼容旧数据，保持字符串 'HH:MM'；后续可以迁移为 TIME 类型
    broadcast_time = Column(String(5), nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    # relationships
    class_ = relationship("Class", foreign_keys=[class_id], back_populates="daily_quotes")
    class_instance = relationship("ClassInstance", foreign_keys=[class_instance_id], back_populates="daily_quotes_instances")

# ---------- OpenWindow ----------
class OpenWindow(Base):
    __tablename__ = "open_windows"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # legacy: class_id 保留
    class_id = Column(Integer, ForeignKey("classes.id", name="fk_ow_class", ondelete="CASCADE"), nullable=True, index=True)

    # 存 "HH:MM"
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)

    # JSON 列：不要在 DDL 里设置默认值
    days_json = Column(MySQLJSON, nullable=True)

    class_ = relationship("Class", foreign_keys=[class_id], back_populates="open_windows")

# ---------- OutgoingQueue ----------
class OutgoingQueue(Base):
    __tablename__ = "outgoing_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_user_id = Column(Integer, nullable=False, index=True)
    payload = Column(MySQLJSON, nullable=False)
    priority = Column(String(16), nullable=False, server_default="normal")
    deliver_after = Column(DateTime, nullable=True)
    delivered = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    delivered_at = Column(DateTime, nullable=True)

# End of file
