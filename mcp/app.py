# mcp/app.py
from fastapi import FastAPI, HTTPException, Query,Depends
from fastapi.responses import JSONResponse,HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, date, time as dtime, timedelta, date as _date
from zoneinfo import ZoneInfo
from sqlalchemy import text, and_, or_,case
from shared.models import OutgoingQueue
from threading import Thread, Event
from typing import Optional, Any, List, Dict
import logging
import asyncio
import json
import requests
import time

# Schema 导入（请确保 shared/schemas.py 已经定义以下类）
from shared.schemas import (
    LeaveMessageCommand, LeaveMessageResponse,
    GetMessagesCommand, GetMessagesResponse, MessageItem,
    PostNoticeCommand, PostNoticeResponse,
    PlayAudioCommand, PlayAudioResponse,
    AddMemoCommand, AddMemoResponse,
    ConfirmMemoCommand, ConfirmMemoResponse,
    GetTodayMemoCommand, GetTodayMemoResponse, MemoItem
)

class OpenWindowModel(BaseModel):
    id: int
    class_id: int
    start_time: str
    end_time: str
    days_json: Optional[List[str]] = None

class OpenWindowCreate(BaseModel):
    class_id: int
    start_time: str
    end_time: str
    days_json: Optional[List[str]] = None

# ORM 导入（请确保 shared/models.py 已正确定义）
from shared.models import (
    User, Message, Memo, Notice, School,
    OpenWindow, NoticeType, Class, DailyQuote, UserRole, Grade, parent_students
)
from .db import init_db, SessionLocal, get_user_id_from_external_id, get_class_id_from_class_code
from werkzeug.security import generate_password_hash, check_password_hash

app = FastAPI(title="Campus Assistant MCP API")

# 初始化数据库（create_all 已在 db.init_db 中实现）
init_db()

BG_LOOP_SLEEP = 30  # 秒；开发阶段短些

# 全局时区：北京时间
TZ = ZoneInfo("Asia/Shanghai")
app.add_middleware(
  CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 默认端口
        "http://localhost:5174",  # Vite 备用端口
        "http://localhost:5175",  # Vite 备用端口
        "http://localhost:5176",  # Vite 备用端口
        "http://192.168.52.1:5174",
        "https://localhost",       # 移动端应用
        "http://localhost",        # 备用
        "capacitor://localhost",   # Capacitor iOS
        "ionic://localhost"        # Ionic
    ],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
logger = logging.getLogger("mcp.delivery")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(ch)
logger.setLevel(logging.INFO)

# 配置
DELIVERY_POLL_INTERVAL = 5  # 秒，轮询间隔
DELIVERY_MODE = "log"       # "log" 或 "http"
DELIVERY_HTTP_CALLBACK: Optional[str] = None

# 线程控制
_delivery_thread: Optional[Thread] = None
_delivery_stop_evt = Event()
_delivery_started = False
_delivery_lock = Event()

# 基础命令模型（与 schemas 中的 Command 对应）
class UserIdentifier(BaseModel):
    user_id: Optional[str] = None
    external_id: Optional[str] = None

class Command(BaseModel):
    command: str
    user_id: str # 将来可以改为 external_id
    role: str
    timestamp: datetime
    context: dict
    
class OutgoingItemModel(BaseModel):
    id: int
    target_user_id: int
    payload: Dict[str, Any]
    priority: str
    deliver_after: Optional[str] = None
    delivered: bool
    created_at: Optional[str] = None
    delivered_at: Optional[str] = None

class PollResponseModel(BaseModel):
    status: str
    items: List[OutgoingItemModel] = []

class EnqueueResponseModel(BaseModel):
    status: str
    enqueue_id: int

class AckResponseModel(BaseModel):
    status: str
    acked: List[int] = []

class OutgoingListResponseModel(BaseModel):
    status: str
    page: int
    size: int
    total: int
    items: List[OutgoingItemModel] = []


class DailyQuoteUpdate(BaseModel):
    content: str


# -------------------- 时间/开放时段辅助函数 --------------------
def now_sh_naive() -> datetime:
    """返回当前北京时间，但去掉 tzinfo（方便存入 DB 的 naive 列）。"""
    return datetime.now(TZ).replace(tzinfo=None)

def ensure_sh(dt: datetime) -> Optional[datetime]:
    """
    把从 DB 读出的 naive 时间或者来自外部的 datetime 转为带 tzinfo 的 Asia/Shanghai。
    如果传入 None 则返回 None。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)

def iso_tz(dt: Optional[datetime]) -> Optional[str]:
    """把 DB 中的 naive 时间转为带 +08:00 的 ISO 字符串，方便返回给前端。"""
    d = ensure_sh(dt)
    return d.isoformat() if d is not None else None

def parse_hm_to_time(hm: str) -> dtime:
    """把 'HH:MM' 转为 datetime.time"""
    h, m = hm.split(":")
    return dtime(int(h), int(m))

def is_now_within_open_windows_for_student(db, student_user_id: int) -> bool:
    """
    支持跨午夜时段判断（Asia/Shanghai）。
    逻辑参见注释。
    """
    user = db.get(User, student_user_id)
    if not user:
        return False

    class_id = None
    for attr in ("class_id", "managed_class_id"):
        if hasattr(user, attr):
            val = getattr(user, attr)
            if val:
                class_id = val
                break

    if class_id is None:
        try:
            res = db.execute(text("SELECT class_id FROM class_students WHERE student_id = :sid LIMIT 1"), {"sid": student_user_id})
            row = res.fetchone()
            if row:
                class_id = row[0]
        except Exception:
            class_id = None

    if class_id is None:
        return False

    rows = db.query(OpenWindow).filter(OpenWindow.class_id == int(class_id)).all()
    if not rows:
        return False

    tz = TZ
    now = datetime.now(tz)
    now_time = now.time()
    weekday_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_name = weekday_map[now.weekday()]
    yesterday_name = weekday_map[(now.weekday() - 1) % 7]

    for w in rows:
        days = w.days_json or []
        if isinstance(days, str):
            try:
                days = json.loads(days)
            except Exception:
                days = []
        days_list = days if days else []

        try:
            start_t = parse_hm_to_time(w.start_time)
            end_t = parse_hm_to_time(w.end_time)
        except Exception:
            continue

        if start_t == end_t:
            if days_list and today_name not in days_list:
                continue
            return True

        if start_t < end_t:
            if days_list and today_name not in days_list:
                continue
            if start_t <= now_time <= end_t:
                return True
            else:
                continue

        # 跨午夜
        if (not days_list or today_name in days_list) and (now_time >= start_t):
            return True
        if (not days_list or yesterday_name in days_list) and (now_time <= end_t):
            return True

    return False

# -------------------- Outgoing queue helper --------------------
def enqueue_message_for_terminal(db_session, msg: Message, priority_override: Optional[str] = None):
    """
    将单条 Message 入库到 outgoing_queue。写入 deliver_after/created_at 都使用 北京时间 naive。
    """
    priority = msg.priority.value if hasattr(msg.priority, "value") else (priority_override or "normal")
    if priority_override:
        priority = priority_override

    # 查询发送者用户名
    sender = db_session.get(User, msg.sender_id)
    sender_name = sender.username if sender else "Unknown"

    payload = {
        "type": "message",
        "message_id": msg.id,
        "sender_id": msg.sender_id,
        "sender_name": sender_name,  # 添加发送者姓名
        "receiver_id": msg.receiver_id,
        # 返回/存 payload 中的 timestamp 使用带时区的 ISO 字符串，便于前端
        "timestamp": iso_tz(msg.timestamp) if getattr(msg, "timestamp", None) else None,
        "content": msg.content,
        "audio_url": msg.audio_url
    }

    deliver_after = None
    # 如果要立即投递（urgent），使用当前北京时间（naive 存 DB）
    if priority == "urgent":
        deliver_after = now_sh_naive()

    oq = OutgoingQueue(
        target_user_id=int(msg.receiver_id),
        payload=payload,
        priority=priority,
        deliver_after=deliver_after,
        created_at=now_sh_naive()
    )
    db_session.add(oq)
    return oq

def enqueue_notice_for_class(db_session, notice_obj: Notice, target_class: Optional[str] = None, target_role: Optional[str] = None):
    """
    把 notice 入队到一组用户。所有时间字段使用北京时间 naive（deliver_after/created_at）。
    返回 created_user_ids 列表。
    """
    payload = {
        "type": "notice",
        "notice_id": notice_obj.id,
        "creator_id": notice_obj.creator_id,
        "content": notice_obj.content,
        # 这里以带时区字符串放入 payload，payload 仅用于前端显示/调试
        "timestamp": iso_tz(notice_obj.timestamp) if getattr(notice_obj, "timestamp", None) else None,
    }
    priority = notice_obj.type.value if hasattr(notice_obj, "type") else "normal"
    deliver_after = None
    if priority == "urgent":
        deliver_after = now_sh_naive()

    created_user_ids = []

    q = db_session.query(User)
    if target_class is not None:
        try:
            cid = int(target_class)
            q = q.filter(User.class_id == cid)
        except Exception:
            return created_user_ids
    elif target_role is not None:
        try:
            q = q.filter(User.role == target_role)
        except Exception:
            return created_user_ids
    else:
        # 默认不广播所有用户（安全）
        return created_user_ids

    users = q.all()
    for u in users:
        oq = OutgoingQueue(
            target_user_id=int(u.id),
            payload=payload,
            priority=priority,
            deliver_after=deliver_after,
            created_at=now_sh_naive()
        )
        db_session.add(oq)
        created_user_ids.append(u.id)

    return created_user_ids

# -------------- helper: 将符合条件的 daily_quotes 入队（一次性执行） --------------
async def enqueue_daily_quotes_once():
    """把当前北京时间对应 minute 的 daily_quote 入队（一次性执行）。"""
    db = SessionLocal()
    try:
        now_sh = datetime.now(TZ)
        hm = now_sh.strftime("%H:%M")  # 'HH:MM'
        quotes = db.query(DailyQuote).filter(
            DailyQuote.active == True,
            DailyQuote.broadcast_time == hm
        ).all()

        if not quotes:
            return {"status": "no_quotes", "checked_time": hm, "count": 0}

        enqueue_count = 0
        for q in quotes:
            class_id = q.class_id
            if not class_id:
                continue
            students = db.query(User).filter(User.class_id == int(class_id)).all()
            for s in students:
                payload = {
                    "type": "daily_quote",
                    "text": q.content,
                    "voice_url": q.voice_url,
                    "class_id": class_id,
                    "quote_id": q.id
                }
                out = OutgoingQueue(
                    target_user_id=int(s.id),
                    payload=payload,
                    priority="normal",
                    deliver_after=None,
                    created_at=now_sh_naive()
                )
                db.add(out)
                enqueue_count += 1
        db.commit()
        return {"status": "enqueued", "time": hm, "enqueued": enqueue_count}
    except Exception as e:
        db.rollback()
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()
        
def sanitize_payload(obj):
    """
    递归把 payload 中的 datetime / date 转为 ISO 字符串，保留其他可序列化类型。
    支持 dict / list / tuple / 基本类型。
    """
    from datetime import datetime as _datetime
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_payload(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_payload(v) for v in obj)
    # datetime -> 带时区的 ISO（使用你现有的 iso_tz 保证是北京时区的字符串）
    if isinstance(obj, _datetime):
        return iso_tz(obj)
    # date -> ISO date
    if isinstance(obj, _date):
        return obj.isoformat()
    # SQLAlchemy/other types that are not JSON serializable but have isoformat
    try:
        # 有些对象（比如 pydantic 的日期/time）也可以通过 isoformat 得到可序列化字符串
        if hasattr(obj, "isoformat") and (not isinstance(obj, (str, bytes))):
            return obj.isoformat()
    except Exception:
        pass
    return obj


# -------------------- 主路由：统一的 MCP 命令入口 --------------------
@app.post("/mcp/command")
async def handle_mcp(cmd: Command):
    db = SessionLocal()
    try:
        # ---------------- leave_message (始终允许) ----------------
        if cmd.command == "leave_message":
            leave_cmd = LeaveMessageCommand(**cmd.dict())
            try:
                # 规范化 timestamp：若来自外部含 tz，先转到北京时间再去掉 tz 存入 DB（naive）
                ts = leave_cmd.timestamp
                if ts is None:
                    ts_naive = now_sh_naive()
                else:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=TZ)
                    ts_naive = ts.astimezone(TZ).replace(tzinfo=None)

                sender_id = get_user_id_from_external_id(db, leave_cmd.user_id) or int(leave_cmd.user_id)
                receiver_id = get_user_id_from_external_id(db, leave_cmd.context.receiver_id) or int(leave_cmd.context.receiver_id)

                if not sender_id or not receiver_id:
                    raise HTTPException(status_code=404, detail="Sender or receiver not found")

                msg = Message(
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    content=leave_cmd.context.content,
                    audio_url=getattr(leave_cmd.context, "audio_url", None),
                    priority=NoticeType(leave_cmd.context.priority),
                    timestamp=ts_naive,
                )
                db.add(msg)
                db.flush()
                # 把 message 加入 outgoing queue（入队函数会设 created_at/deliver_after）
                enqueue_message_for_terminal(db, msg)
                db.commit()
                db.refresh(msg)
                return LeaveMessageResponse(status="success", message_id=msg.id, detail=None)
            except Exception as e:
                db.rollback()
                return LeaveMessageResponse(status="error", message_id=None, detail=str(e))

        # ---------------- get_messages (受限：学生仅开放时段) ----------------
        elif cmd.command == "get_messages":
            get_cmd = GetMessagesCommand(**cmd.dict())
            user_id = get_user_id_from_external_id(db, cmd.user_id) or int(cmd.user_id)
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")

            if cmd.role == "student":
                if not is_now_within_open_windows_for_student(db, user_id):
                    return GetMessagesResponse(status="error", messages=[], detail="Not within open time window")
            try:
                rows = db.query(Message).filter(Message.receiver_id == user_id).order_by(Message.timestamp.desc()).all()
                
                sender_ids = {m.sender_id for m in rows}
                senders = db.query(User).filter(User.id.in_(sender_ids)).all()
                sender_map = {s.id: s.username for s in senders}

                items = [
                    {
                        "id": m.id,
                        "sender_id": str(m.sender_id),
                        "name": sender_map.get(m.sender_id, "Unknown"),
                        "content": m.content,
                        "audio_url": m.audio_url,
                        "priority": m.priority.value if hasattr(m.priority, "value") else str(m.priority),
                        "timestamp": iso_tz(m.timestamp)
                    } for m in rows
                ]
                return {"status": "success", "messages": items, "detail": None}
            except Exception as e:
                return {"status": "error", "messages": [], "detail": str(e)}

        # ---------------- play_audio (受限：学生仅开放时段) ----------------
        elif cmd.command == "play_audio":
            play_cmd = PlayAudioCommand(**cmd.dict())
            user_id = get_user_id_from_external_id(db, cmd.user_id) or int(cmd.user_id)
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")

            if cmd.role == "student":
                if not is_now_within_open_windows_for_student(db, user_id):
                    return PlayAudioResponse(status="error", audio_url=None, detail="Not within open time window")
            try:
                msg = db.get(Message, play_cmd.context.message_id)
                if not msg or not msg.audio_url:
                    return PlayAudioResponse(status="error", audio_url=None, detail="No audio available")
                return PlayAudioResponse(status="success", audio_url=msg.audio_url, detail=None)
            except Exception as e:
                return PlayAudioResponse(status="error", audio_url=None, detail=str(e))

        # ---------------- add_memo (受限：学生仅开放时段) ----------------
        elif cmd.command == "add_memo":
            add_cmd = AddMemoCommand(**cmd.dict())
            user_id = get_user_id_from_external_id(db, cmd.user_id) or int(cmd.user_id)
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")

            if cmd.role == "student":
                if not is_now_within_open_windows_for_student(db, user_id):
                    return AddMemoResponse(status="error", memo_id=None, detail="Not within open time window")
            try:
                remind_date = add_cmd.context.remind_date
                # 如果是 datetime -> 把其转到北京时区再取 date
                if isinstance(remind_date, datetime):
                    if remind_date.tzinfo is None:
                        remind_date = remind_date.replace(tzinfo=TZ)
                    remind_date = remind_date.astimezone(TZ).date()

                memo = Memo(
                    student_id=user_id,
                    content=add_cmd.context.content,
                    remind_date=remind_date
                )
                db.add(memo)
                db.commit()
                db.refresh(memo)
                return AddMemoResponse(status="success", memo_id=memo.id, detail=None)
            except Exception as e:
                db.rollback()
                return AddMemoResponse(status="error", memo_id=None, detail=str(e))

        # ---------------- confirm_memo (受限：学生仅开放时段) ----------------
        elif cmd.command == "confirm_memo":
            confirm_cmd = ConfirmMemoCommand(**cmd.dict())
            user_id = get_user_id_from_external_id(db, cmd.user_id) or int(cmd.user_id)
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")

            if cmd.role == "student":
                if not is_now_within_open_windows_for_student(db, user_id):
                    return ConfirmMemoResponse(status="error", detail="Not within open time window")
            try:
                memo = db.get(Memo, confirm_cmd.context.memo_id)
                if not memo:
                    return ConfirmMemoResponse(status="error", detail="Memo not found")
                db.delete(memo)
                db.commit()
                return ConfirmMemoResponse(status="success", detail=None)
            except Exception as e:
                db.rollback()
                return ConfirmMemoResponse(status="error", detail=str(e))

        # ---------------- get_today_memo (受限：学生仅开放时段) ----------------
        elif cmd.command == "get_today_memo":
            get_cmd = GetTodayMemoCommand(**cmd.dict())
            user_id = get_user_id_from_external_id(db, cmd.user_id) or int(cmd.user_id)
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")

            if cmd.role == "student":
                if not is_now_within_open_windows_for_student(db, user_id):
                    return GetTodayMemoResponse(status="error", memos=[], detail="Not within open time window")
            try:
                today = datetime.now(TZ).date()
                rows = db.query(Memo).filter(Memo.student_id == user_id, Memo.remind_date == today).all()
                items = [{"id": m.id, "content": m.content, "remind_date": m.remind_date} for m in rows]
                return GetTodayMemoResponse(status="success", memos=items, detail=None)
            except Exception as e:
                return GetTodayMemoResponse(status="error", memos=[], detail=str(e))

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported command: {cmd.command}")

    finally:
        db.close()

# -------------------- 后台调度与入队循环 --------------------
async def background_scheduler_loop():
    """长期运行的调度循环：检查 memo reminders 与 daily quotes（已加强去重与北京时间一致性）。"""
    tz = TZ
    while True:
        try:
            db = SessionLocal()
            now_sh = datetime.now(tz)
            today = now_sh.date()
            now_time = now_sh.time()

            # 为当天范围做 naive 时间边界（与 DB 中存储的 naive 北京时间一致）
            start_today_naive = datetime(today.year, today.month, today.day)
            start_tomorrow_naive = start_today_naive + timedelta(days=1)

            # -------------------- 1) memo 提醒 --------------------
            memos = db.query(Memo).filter(Memo.remind_date == today).all()
            # 内存集合：避免同一循环内重复入队
            created_set = set()
            for m in memos:
                # 找学生与班级
                student = db.get(User, int(m.student_id))
                class_id = None
                if student:
                    class_id = getattr(student, "class_id", None) or getattr(student, "managed_class_id", None)
                if not class_id:
                    continue

                open_windows = db.query(OpenWindow).filter(OpenWindow.class_id == int(class_id)).all()
                if not open_windows:
                    continue

                for w in open_windows:
                    # 解析 start/end（兼容字符串或 time-like）
                    try:
                        st = parse_hm_to_time(w.start_time)
                        et = parse_hm_to_time(w.end_time)
                    except Exception:
                        # 忽略此窗口配置
                        continue

                    # days_json 解析
                    days = w.days_json or []
                    if isinstance(days, str):
                        try:
                            days = json.loads(days)
                        except Exception:
                            days = []
                    days_list = days if days else []

                    # 判断是否在窗口内（含跨午夜）
                    in_window = False
                    if st == et:
                        in_window = True
                    elif st < et:
                        in_window = (st <= now_time <= et)
                    else:
                        # 跨午夜：若现在 >= start 或 now <= end 则匹配
                        if now_time >= st or now_time <= et:
                            in_window = True

                    # 如果配置了 days 并且今天不在其中 -> 跳过
                    weekday_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    today_name = weekday_map[now_sh.weekday()]
                    if days_list and (today_name not in days_list):
                        in_window = False

                    if not in_window:
                        continue

                    # 内存去重 key
                    key = (int(m.student_id), int(m.id), int(w.id))
                    if key in created_set:
                        continue

                    # DB 去重：按 target_user_id + payload contains + 当天 created_at 范围
                    try:
                        exists = db.query(OutgoingQueue).filter(
                            OutgoingQueue.target_user_id == int(m.student_id),
                            OutgoingQueue.payload.contains({
                                "type": "memo_reminder",
                                "memo_id": m.id,
                                "open_window_id": w.id
                            }),
                            OutgoingQueue.created_at >= start_today_naive,
                            OutgoingQueue.created_at < start_tomorrow_naive
                        ).first()
                    except Exception:
                        # 若数据库无法支持 JSON contains 或者报错，则退回到只按 target_user_id + payload.contains 的判断（尽量保守）
                        try:
                            exists = db.query(OutgoingQueue).filter(
                                OutgoingQueue.target_user_id == int(m.student_id),
                                OutgoingQueue.payload.contains({
                                    "type": "memo_reminder",
                                    "memo_id": m.id,
                                    "open_window_id": w.id
                                })
                            ).first()
                        except Exception:
                            exists = None

                    if exists:
                        continue

                    # 入队（使用北京时间 naive 存 created_at / deliver_after）
                    oq = OutgoingQueue(
                        target_user_id=int(m.student_id),
                        payload={
                            "type": "memo_reminder",
                            "memo_id": m.id,
                            "open_window_id": w.id,
                            "content": m.content,
                        },
                        priority="normal",
                        deliver_after=now_sh_naive(),
                        created_at=now_sh_naive()
                    )
                    db.add(oq)
                    created_set.add(key)

            # 如果有新增则 commit 一次
            if created_set:
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Failed to commit memo reminders")

            # -------------------- 2) 每日鸡汤：按 broadcast_time 入队（按分钟匹配） --------------------
            try:
                dq_rows = db.execute(text("SELECT id, class_id, content, broadcast_time FROM daily_quotes WHERE active=1")).fetchall()
            except Exception:
                dq_rows = []

            daily_created_set = set()
            for dq in dq_rows:
                try:
                    scheduled_hm = dq["broadcast_time"]
                    sh = dtime.fromisoformat(scheduled_hm)
                except Exception:
                    continue

                # 在同一分钟匹配
                if now_time.hour == sh.hour and now_time.minute == sh.minute:
                    # 为每个目标用户去重并入队
                    try:
                        users = db.query(User).filter(User.class_id == int(dq["class_id"])).all()
                    except Exception:
                        users = []

                    for u in users:
                        key = (int(u.id), int(dq["id"]))
                        if key in daily_created_set:
                            continue

                        # DB 去重：按 target_user_id + payload contains + 当天 created_at 范围
                        try:
                            exists = db.query(OutgoingQueue).filter(
                                OutgoingQueue.target_user_id == int(u.id),
                                OutgoingQueue.payload.contains({
                                    "type": "daily_quote",
                                    "quote_id": dq["id"],
                                    "date": today.isoformat()
                                }),
                                OutgoingQueue.created_at >= start_today_naive,
                                OutgoingQueue.created_at < start_tomorrow_naive
                            ).first()
                        except Exception:
                            try:
                                exists = db.query(OutgoingQueue).filter(
                                    OutgoingQueue.target_user_id == int(u.id),
                                    OutgoingQueue.payload.contains({
                                        "type": "daily_quote",
                                        "quote_id": dq["id"],
                                        "date": today.isoformat()
                                    })
                                ).first()
                            except Exception:
                                exists = None

                        if exists:
                            continue

                        oq = OutgoingQueue(
                            target_user_id=int(u.id),
                            payload={
                                "type": "daily_quote",
                                "quote_id": int(dq["id"]),
                                "content": dq["content"],
                                "date": today.isoformat()
                            },
                            priority="normal",
                            deliver_after=now_sh_naive(),
                            created_at=now_sh_naive()
                        )
                        db.add(oq)
                        daily_created_set.add(key)

            if daily_created_set:
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Failed to commit daily_quote enqueues")

        except Exception as e:
            # 记录错误但不要让循环停止
            try:
                logger.exception("Scheduler error: %s", str(e))
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass

        await asyncio.sleep(BG_LOOP_SLEEP)


def _find_daily_quote_for_class(db, class_id: int):
    """
    兼容 MySQL 的查找逻辑（优先当天 date，再通用 date IS NULL）。
    """
    today = datetime.now(TZ).date()

    q = (
        db.query(DailyQuote)
          .filter(
              DailyQuote.class_id == class_id,
              DailyQuote.active == True,
              DailyQuote.date == today
          )
          .order_by(DailyQuote.id.desc())
          .first()
    )
    if q:
        return q

    q = (
        db.query(DailyQuote)
          .filter(
              DailyQuote.class_id == class_id,
              DailyQuote.active == True,
              DailyQuote.date == None
          )
          .order_by(DailyQuote.id.desc())
          .first()
    )
    return q

def _deliver_due_once():
    """运行一次投递扫描并尝试投递到目标（同步）。所有时间比较以北京时间 naive 为准。"""
    db = SessionLocal()
    try:
        now_naive = now_sh_naive()
        due_rows = db.query(OutgoingQueue).filter(
            OutgoingQueue.delivered == False,
            or_(
                OutgoingQueue.deliver_after == None,
                OutgoingQueue.deliver_after <= now_naive
            )
        ).order_by(OutgoingQueue.priority.desc(), OutgoingQueue.created_at.asc()).limit(50).all()

        if not due_rows:
            return {"count": 0}

        processed = []
        for r in due_rows:
            payload = r.payload or {}
            queue_id = r.id
            success = False
            err = None
            if DELIVERY_MODE == "http" and DELIVERY_HTTP_CALLBACK:
                try:
                    resp = requests.post(DELIVERY_HTTP_CALLBACK, json={
                        "queue_id": queue_id,
                        "target_user_id": r.target_user_id,
                        "payload": payload
                    }, timeout=5)
                    success = 200 <= resp.status_code < 300
                    if not success:
                        err = f"callback_status:{resp.status_code}"
                except Exception as e:
                    err = str(e)
                    success = False
            else:
                logger.info("Deliver (log-mode) queue_id=%s target_user=%s payload=%s", queue_id, r.target_user_id, payload)
                success = True

            if success:
                try:
                    # 标记为已投递（使用北京时间 naive 存入 DB）
                    r.delivered = True
                    r.delivered_at = now_naive
                    db.add(r)
                    db.commit()
                    processed.append(queue_id)
                except Exception as e:
                    db.rollback()
                    logger.exception("commit failed for queue_id=%s", queue_id)
            else:
                logger.warning("Delivery failed queue_id=%s: %s", queue_id, err)

        return {"count": len(processed), "processed": processed}
    finally:
        db.close()

def _delivery_loop(poll_interval: int = DELIVERY_POLL_INTERVAL):
    logger.info("Delivery loop started (interval=%s)", poll_interval)
    while not _delivery_stop_evt.wait(poll_interval):
        try:
            res = _deliver_due_once()
            if res and res.get("count", 0) > 0:
                logger.info("Delivered %d items: %s", res.get("count", 0), res.get("processed"))
        except Exception:
            logger.exception("Unhandled error in delivery loop")
    logger.info("Delivery loop stopped")

# -------------------- 单独的发布通知接口（教师/班主任用） --------------------
@app.post("/mcp/notice", response_model=PostNoticeResponse)
async def post_notice(cmd: PostNoticeCommand):
    db = SessionLocal()
    try:
        # 规范化 timestamp 为 北京时间 naive 再存
        ts = cmd.timestamp
        if ts is None:
            ts_naive = now_sh_naive()
        else:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=TZ)
            ts_naive = ts.astimezone(TZ).replace(tzinfo=None)

        notice = Notice(
            creator_id=int(cmd.user_id),
            content=cmd.context.content,
            type=NoticeType(cmd.context.priority),
            timestamp=ts_naive
        )
        db.add(notice)
        db.commit()
        db.refresh(notice)

        # 决定收件人列表
        recipients = []
        tc = getattr(cmd.context, "target_class", None)
        tr = getattr(cmd.context, "target_role", None)

        if tc:
            class_id = get_class_id_from_class_code(db, tc)
            if class_id:
                users_q = db.query(User).filter(User.class_id == class_id).all()
            else:
                try:
                    class_id_int = int(tc)
                    users_q = db.query(User).filter(User.class_id == class_id_int).all()
                except Exception:
                    users_q = db.query(User).join(Class).filter(Class.name == str(tc)).all()
            recipients.extend(users_q)

        if tr:
            try:
                role_enum = UserRole(tr)
                users_by_role = db.query(User).filter(User.role == role_enum).all()
            except Exception:
                users_by_role = db.query(User).filter(User.role == tr).all()
            for u in users_by_role:
                if u not in recipients:
                    recipients.append(u)

        if not recipients:
            recipients = db.query(User).all()

        enqueued = 0
        for u in recipients:
            existing_rows = db.query(OutgoingQueue).filter(
                OutgoingQueue.target_user_id == int(u.id),
                OutgoingQueue.delivered == False
            ).all()

            skip = False
            for ex in existing_rows:
                try:
                    nid = ex.payload.get("notice_id")
                except Exception:
                    nid = None
                if nid is not None and str(nid) == str(notice.id):
                    skip = True
                    break
            if skip:
                continue

            payload = {
                "type": "notice",
                "text": notice.content,
                "notice_id": notice.id,
                "creator_id": notice.creator_id,
                "priority": notice.type.value if hasattr(notice.type, "value") else str(notice.type),
                "timestamp": iso_tz(notice.timestamp)
            }

            oq = OutgoingQueue(
                target_user_id=int(u.id),
                payload=payload,
                priority=payload["priority"] or "normal",
                deliver_after=None,
                created_at=now_sh_naive()
            )
            db.add(oq)
            enqueued += 1

        db.commit()
        return PostNoticeResponse(status="success", notice_id=notice.id, detail=f"enqueued:{enqueued}")

    except Exception as e:
        db.rollback()
        return PostNoticeResponse(status="error", notice_id=None, detail=str(e))
    finally:
        db.close()

@app.get("/mcp/debug_openwindow/{user_id}")
def debug_openwindow(user_id: int):
    db = SessionLocal()
    try:
        # 当前时间（UTC 和 北京时间）
        now_utc = datetime.utcnow().isoformat() + "Z"
        now_sh = datetime.now(TZ).isoformat()
        weekday_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        today_name = weekday_map[datetime.now(TZ).weekday()]

        user = db.get(User, user_id)
        user_info = None
        class_id = None
        if user:
            user_info = {"id": user.id, "username": getattr(user, "username", None),
                         "class_id": getattr(user, "class_id", None),
                         "managed_class_id": getattr(user, "managed_class_id", None)}
            class_id = user_info["class_id"] or user_info["managed_class_id"]

        rows = []
        if class_id:
            q = db.query(OpenWindow).filter(OpenWindow.class_id == int(class_id)).all()
            for w in q:
                rows.append({
                    "id": w.id,
                    "start_time": w.start_time,
                    "end_time": w.end_time,
                    "days_json": w.days_json
                })

        allowed = is_now_within_open_windows_for_student(db, user_id)

        return {
            "now_utc": now_utc,
            "now_shanghai": now_sh,
            "today_name": today_name,
            "user_info": user_info,
            "class_id_used": class_id,
            "open_windows_rows": rows,
            "is_allowed": allowed
        }
    finally:
        db.close()

# -------- POST /mcp/enqueue --------
@app.post("/mcp/enqueue", response_model=EnqueueResponseModel, tags=["admin"])
async def enqueue_item(item: dict):
    db = SessionLocal()
    try:
        tid = int(item.get("target_user_id"))
        payload = item.get("payload") or {}
        priority = item.get("priority") or "normal"
        da = item.get("deliver_after")
        deliver_after = None
        if da:
            parsed = datetime.fromisoformat(da)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=TZ)
            deliver_after = parsed.astimezone(TZ).replace(tzinfo=None)
        created_at = now_sh_naive()

        q = OutgoingQueue(
            target_user_id=tid,
            payload=payload,
            priority=priority,
            deliver_after=deliver_after,
            created_at=created_at
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        return {"status": "success", "enqueue_id": q.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# -------- GET /mcp/poll --------
@app.get("/mcp/poll")
async def poll(user_id: int = Query(...), timeout: int = Query(0)):
    """
    Poll endpoint: 返回可投递项（已对 payload 做 sanitize，避免 datetime 等无法序列化导致 500）。
    """
    deadline = time.time() + max(0, int(timeout))
    while True:
        db = SessionLocal()
        try:
            # 使用北京时间 naive 与 DB 中的 naive 时间比较（与你代码风格保持一致）
            now_naive = now_sh_naive()
            rows = db.query(OutgoingQueue).filter(
                OutgoingQueue.target_user_id == int(user_id),
                OutgoingQueue.delivered == False,
                or_(
                    OutgoingQueue.deliver_after == None,
                    OutgoingQueue.deliver_after <= now_naive
                )
            ).order_by(
                OutgoingQueue.priority.desc(), OutgoingQueue.created_at.asc()
            ).limit(10).all()
            if rows:
                items = []
                for r in rows:
                    # 深度清洗 payload，保证 JSON 可序列化
                    raw_payload = r.payload or {}
                    safe_payload = sanitize_payload(raw_payload)

                    items.append({
                        "id": r.id,
                        "payload": safe_payload,
                        "priority": r.priority,
                        # 返回带时区的 ISO 字符串（对模型中的时间字段做转换）
                        "created_at": iso_tz(r.created_at),
                        "deliver_after": iso_tz(r.deliver_after)
                    })
                return {"status": "success", "items": items}
        finally:
            db.close()

        if time.time() >= deadline:
            return {"status": "success", "items": []}
        time.sleep(0.8)

# -------- POST /mcp/ack --------
@app.post("/mcp/ack", response_model=AckResponseModel, tags=["terminal"])
def ack_items(body: dict):
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids required")
    db = SessionLocal()
    try:
        now_naive = now_sh_naive()
        rows = db.query(OutgoingQueue).filter(OutgoingQueue.id.in_(ids)).all()
        updated = []
        for r in rows:
            r.delivered = True
            r.delivered_at = now_naive
            updated.append(r.id)
        db.commit()
        return {"status": "success", "acked": updated}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.on_event("startup")
async def start_background_scheduler():
    loop = asyncio.get_event_loop()
    app.state._bg_task = loop.create_task(background_scheduler_loop())
    print("Background scheduler started.")

@app.on_event("shutdown")
async def stop_background_scheduler():
    task = getattr(app.state, "_bg_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        print("Background scheduler stopped.")

@app.get("/mcp/daily_quote/{class_id}")
def get_daily_quote(class_id: int):
    db = SessionLocal()
    try:
        q = _find_daily_quote_for_class(db, class_id)
        if not q:
            return {"status": "error", "detail": "No daily quote for today", "quote": None}
        return {
            "status": "success",
            "quote": {
                "id": q.id,
                "class_id": q.class_id,
                "date": q.date.isoformat() if q.date else None,
                "content": q.content,
                "voice_url": q.voice_url,
                "broadcast_time": q.broadcast_time,
                "active": q.active
            }
        }
    finally:
        db.close()


@app.put("/mcp/daily_quote/{quote_id}")
def update_daily_quote(quote_id: int, body: DailyQuoteUpdate, requester_id: int = Query(...)):
    """更新每日鸡汤的内容（仅限教师）。"""
    db = SessionLocal()
    try:
        # 权限检查：请求者必须是教师
        requester = db.get(User, requester_id)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        is_teacher = getattr(requester, "role", None) == UserRole.teacher
        if not is_teacher:
            raise HTTPException(status_code=403, detail="permission denied: only teachers can update quotes")

        # 查找并更新 quote
        quote = db.get(DailyQuote, quote_id)
        if not quote:
            raise HTTPException(status_code=404, detail="DailyQuote not found")

        # 权限：老师只能改自己班的
        if requester.managed_class_id != quote.class_id:
            raise HTTPException(status_code=403, detail="Permission denied: cannot update quote for another class")

        quote.content = body.content
        db.commit()
        db.refresh(quote)

        return {
            "status": "success",
            "quote": {
                "id": quote.id,
                "content": quote.content,
            }
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/mcp/broadcast_daily/{class_id}")
def broadcast_daily_quote(class_id: int):
    db = SessionLocal()
    try:
        q = _find_daily_quote_for_class(db, class_id)
        if not q:
            return {"status": "error", "detail": "No daily quote to broadcast", "enqueued": 0}

        students = db.query(User).filter(User.class_id == class_id, User.role == UserRole.student).all()
        if not students:
            return {"status": "error", "detail": "No students in class", "enqueued": 0}

        enqueued = 0
        for s in students:
            payload = {
                "type": "daily_quote",
                "text": q.content,
                "voice_url": q.voice_url,
                "broadcast_time": q.broadcast_time
            }
            item = OutgoingQueue(
                target_user_id=s.id,
                payload=payload,
                priority="normal",
                deliver_after=None,
                created_at=now_sh_naive()
            )
            db.add(item)
            enqueued += 1

        db.commit()
        return {"status": "success", "detail": f"Enqueued {enqueued} items", "enqueued": enqueued}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/mcp/trigger_daily_quote/{quote_id}")
def trigger_daily_quote(quote_id: int):
    db = SessionLocal()
    try:
        quote = db.get(DailyQuote, quote_id)
        if not quote or (hasattr(quote, "active") and not quote.active):
            raise HTTPException(status_code=404, detail="daily_quote not found or inactive")

        if quote.class_id:
            users = db.query(User).filter(User.class_id == int(quote.class_id)).all()
        else:
            users = db.query(User).filter(User.role == UserRole.student).all()

        if not users:
            return {"status": "success", "enqueued": 0, "detail": "no target users"}

        enqueued = 0
        for u in users:
            payload = {
                "type": "daily_quote",
                "quote_id": quote.id,
                "content": quote.content,
                "voice_url": getattr(quote, "voice_url", None),
                "broadcast_time": getattr(quote, "broadcast_time", None)
            }
            q = OutgoingQueue(
                target_user_id=int(u.id),
                payload=payload,
                priority="normal",
                created_at=now_sh_naive()
            )
            db.add(q)
            enqueued += 1

        db.commit()
        return {"status": "success", "enqueued": enqueued}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/mcp/trigger_daily_quotes")
async def trigger_daily_quotes():
    task = asyncio.create_task(enqueue_daily_quotes_once())
    return {"status": "triggered"}

# -------------- 启动时后台循环（每分钟检查一次并入队） --------------
async def daily_scheduler_loop():
    """后台循环：每分钟检查一次并入队。"""
    tz = TZ
    while True:
        try:
            await enqueue_daily_quotes_once()
        except Exception:
            pass
        now = datetime.now(tz)
        sec_to_next = 60 - now.second
        await asyncio.sleep(sec_to_next)

@app.on_event("startup")
async def start_background_daily_scheduler():
    asyncio.create_task(daily_scheduler_loop())

@app.get("/mcp/outgoing/list", response_model=OutgoingListResponseModel, tags=["admin"])
def outgoing_list(
    requester_id: int = Query(..., description="发起查询的用户 id（用于权限校验）"),
    target_user_id: int | None = Query(None, description="可选：按 target_user_id 过滤"),
    delivered: int | None = Query(None, description="可选：0/1 过滤 delivered 状态"),
    priority: str | None = Query(None, description="可选：按 priority 过滤（e.g. urgent/normal）"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(20, ge=1, le=200, description="每页大小，最大200")
):
    """
    管理接口（分页 + 按 priority 排序 + 简单权限检查）。
    说明：
      - 必须传 requester_id（用来校验权限）。只有 teacher 或 role 为 'admin' 的用户可查看。
      - 支持按 target_user_id / delivered / priority 过滤。
      - 按 (priority urgent 首) + created_at desc 排序。
    """
    db = SessionLocal()
    try:
        # 1. 权限检查：请求者必须存在，且为 teacher 或 admin（兼容字符串或 Enum）
        requester = db.get(User, requester_id)
        logger.info(f"Requester found: {requester}")
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        # 允许的条件： role == UserRole.teacher 或 role 字符串为 'admin'
        allowed = False
        try:
            # requester.role 可能是 Enum，也可能是字符串（根据你的模型）
            rrole = getattr(requester, "role", None)
            logger.info(f"Requester role: {rrole}")
            if rrole is not None:
                # 直接比较 Enum 类型，更安全
                if rrole == UserRole.admin:
                    allowed = True
        except Exception as e:
            logger.error(f"Error checking role: {e}")
            allowed = False

        if not allowed:
            raise HTTPException(status_code=403, detail="permission denied: only admin allowed")

        # 2. 构造查询（可复用 q 来做 count 和分页查询）
        q = db.query(OutgoingQueue)
        if target_user_id is not None:
            q = q.filter(OutgoingQueue.target_user_id == int(target_user_id))
        if delivered is not None:
            # 传 0/1 -> 转为 bool
            q = q.filter(OutgoingQueue.delivered == bool(int(delivered)))
        if priority is not None:
            q = q.filter(OutgoingQueue.priority == str(priority))

        # 3. 计算总数（用于分页元数据）
        total = q.count()

        # 4. 优先按 priority 排序（urgent 首），其次按 created_at 降序
        #    使用 SQLAlchemy case：urgent -> 1, else 0，然后 desc()
        priority_case = case((OutgoingQueue.priority == "urgent", 1), else_=0)
        q = q.order_by(priority_case.desc(), OutgoingQueue.created_at.desc())

        # 5. 分页 offset/limit
        offset = (page - 1) * size
        rows = q.offset(offset).limit(size).all()

        # 6. 构造返回项（对时间做时区友好输出）
        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "target_user_id": r.target_user_id,
                "payload": r.payload,
                "priority": r.priority,
                "deliver_after": iso_tz(r.deliver_after),
                "delivered": bool(r.delivered),
                "created_at": iso_tz(r.created_at),
                "delivered_at": iso_tz(r.delivered_at)
            })

        return {
            "status": "success",
            "page": page,
            "size": size,
            "total": total,
            "items": items
        }
    finally:
        db.close()


@app.post("/mcp/outgoing/mark_delivered")
def mark_outgoing_delivered(body: dict):
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids required")
    db = SessionLocal()
    try:
        now_naive = now_sh_naive()
        rows = db.query(OutgoingQueue).filter(OutgoingQueue.id.in_(ids)).all()
        updated = []
        for r in rows:
            r.delivered = True
            r.delivered_at = now_naive
            updated.append(r.id)
        db.commit()
        return {"status": "success", "marked": updated}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/mcp/outgoing/delete")
def delete_outgoing(body: dict):
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids required")
    db = SessionLocal()
    try:
        rows = db.query(OutgoingQueue).filter(OutgoingQueue.id.in_(ids)).all()
        deleted = [r.id for r in rows]
        for r in rows:
            db.delete(r)
        db.commit()
        return {"status": "success", "deleted": deleted}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

#@app.on_event("startup")
#def _start_delivery_thread():
    #global _delivery_thread, _delivery_started
    #if _delivery_started:
        #return
    #_delivery_started = True
    #_delivery_stop_evt.clear()
    #_delivery_thread = Thread(target=_delivery_loop, args=(DELIVERY_POLL_INTERVAL,), daemon=True)
    #_delivery_thread.start()
    #logger.info("Background delivery thread started.")

@app.on_event("shutdown")
def _stop_delivery_thread():
    global _delivery_thread, _delivery_started
    _delivery_stop_evt.set()
    if _delivery_thread and _delivery_thread.is_alive():
        _delivery_thread.join(timeout=2)
    _delivery_started = False
    logger.info("Background delivery thread stopped.")

# 管理接口：查看/设置 delivery 配置
@app.get("/mcp/delivery/status")
def delivery_status():
    return {
        "running": _delivery_started,
        "mode": DELIVERY_MODE,
        "callback": DELIVERY_HTTP_CALLBACK,
        "poll_interval": DELIVERY_POLL_INTERVAL
    }

@app.post("/mcp/delivery/config")
def delivery_config(body: dict):
    global DELIVERY_MODE, DELIVERY_HTTP_CALLBACK, DELIVERY_POLL_INTERVAL
    m = body.get("mode")
    cb = body.get("callback")
    pi = body.get("poll_interval")
    if m:
        if m not in ("log", "http"):
            raise HTTPException(status_code=400, detail="mode must be 'log' or 'http'")
        DELIVERY_MODE = m
    if cb is not None:
        DELIVERY_HTTP_CALLBACK = cb
    if pi is not None:
        try:
            DELIVERY_POLL_INTERVAL = int(pi)
        except Exception:
            raise HTTPException(status_code=400, detail="poll_interval must be int")
    return {"status": "ok", "mode": DELIVERY_MODE, "callback": DELIVERY_HTTP_CALLBACK, "poll_interval": DELIVERY_POLL_INTERVAL}

@app.post("/mcp/delivery/trigger")
def delivery_trigger():
    try:
        res = _deliver_due_once()
        return {"status": "ok", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/delivery/mock_callback")
def delivery_mock_callback(payload: dict):
    logger.info("Mock callback received: %s", payload)
    return {"status": "ok"}

@app.post("/mcp/delivery/stop")
def delivery_stop():
    global _delivery_thread, _delivery_started
    _delivery_stop_evt.set()
    if _delivery_thread and _delivery_thread.is_alive():
        _delivery_thread.join(timeout=2)
    _delivery_started = False
    return {"status": "stopped"}

@app.post("/mcp/delivery/start")
def delivery_start():
    global _delivery_thread, _delivery_started
    if _delivery_started:
        return {"status": "already_running"}
    _delivery_stop_evt.clear()
    _delivery_thread = Thread(target=_delivery_loop, args=(DELIVERY_POLL_INTERVAL,), daemon=True)
    _delivery_thread.start()
    _delivery_started = True
    return {"status": "started"}

@app.post("/mcp/grades/add")
def add_grade(body: dict):
    """
    老师录入成绩（简单权限校验：requester_id 必须是 teacher）
    Body:
    {
      "requester_id": "ext123",
      "student_id": "ext456",
      "subject": "Math",
      "score": 95,
      "semester": "2025-1"
    }
    """
    requester_id_str = body.get("requester_id")
    if requester_id_str is None:
        raise HTTPException(status_code=400, detail="requester_id required")
    db = SessionLocal()
    try:
        # 使用 get_user_id_from_external_id 正确映射 external_id 到内部 id
        requester_id = get_user_id_from_external_id(db, requester_id_str)
        if not requester_id:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")
        # 简单权限：必须是 teacher（或 future: admin）
        try:
            if requester.role != UserRole.teacher:
                raise HTTPException(status_code=403, detail="permission denied, only teacher can add grades")
        except Exception:
            # 若 role 存储为字符串也兼容
            if str(requester.role) != str(UserRole.teacher):
                raise HTTPException(status_code=403, detail="permission denied, only teacher can add grades")

        student_id_str = body.get("student_id")
        subject = body.get("subject")
        score = body.get("score")
        semester = body.get("semester") or ""

        if not all([student_id_str, subject, score is not None]):
            raise HTTPException(status_code=400, detail="student_id, subject, score required")

        # 使用 get_user_id_from_external_id 正确映射 student external_id 到内部 id
        student_id = get_user_id_from_external_id(db, student_id_str)
        if not student_id:
            raise HTTPException(status_code=404, detail="Student not found")

        # 权限：老师只能给自己的班级学生加成绩
        student = db.get(User, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role == 'teacher':
            if student.class_id != requester.managed_class_id:
                raise HTTPException(status_code=403, detail="Permission denied: cannot add grade for student in another class")

        g = Grade(
            student_id=student_id,
            subject=str(subject),
            score=int(score),
            semester=str(semester),
            teacher_id=requester_id
        )
        db.add(g)
        db.commit()
        db.refresh(g)
        return {"status": "success", "grade_id": g.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/mcp/grades/student/{student_identifier}")
def get_grades_for_student(student_identifier: str, requester_id: str = Query(...)):
    """
    查看某学生成绩（可由老师/该学生/家长查看）
    请求示例: /mcp/grades/student/ext456?requester_id=ext123
    """
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        student_id = get_user_id_from_external_id(db, student_identifier) or int(student_identifier)
        if not student_id:
            raise HTTPException(status_code=404, detail="Student not found")

        # 权限逻辑：
        # - requester 是该 student 自己（id==student_id） -> 允许
        # - requester.role == teacher -> 允许
        # - requester 是该学生家长 -> 允许
        if requester_id_internal != student_id:
            requester_role = getattr(requester.role, 'value', requester.role)
            
            # 如果是教师，允许访问
            if requester_role == 'teacher':
                pass
            # 如果是家长，检查是否是孩子的家长
            elif requester_role == 'parent':
                # 检查家长是否与目标学生有关联
                parent_child_relation = db.query(parent_students).filter(
                    parent_students.c.parent_id == requester_id_internal,
                    parent_students.c.student_id == student_id
                ).first()
                
                if not parent_child_relation:
                    raise HTTPException(status_code=403, detail="Permission denied: not the parent of this student")
            else:
                # 其他角色不允许访问
                raise HTTPException(status_code=403, detail="permission denied")

        rows = db.query(Grade).filter(Grade.student_id == student_id).order_by(Grade.semester.desc(), Grade.subject.asc()).all()
        items = [{"id": r.id, "subject": r.subject, "score": r.score, "semester": r.semester, "teacher_id": r.teacher_id} for r in rows]
        return {"status": "success", "student_id": student_id, "grades": items}
    finally:
        db.close()

@app.get("/mcp/grades/class/{class_identifier}")
def get_grades_for_class(class_identifier: str, subject: Optional[str] = Query(None), semester: Optional[str] = Query(None), requester_id: str = Query(...), page: int = Query(1), size: int = Query(50)):
    """
    按班级查询成绩（分页）。
    仅允许老师或管理员查看。
    """
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")
        
        class_id = get_class_id_from_class_code(db, class_identifier) or int(class_identifier)
        if not class_id:
            raise HTTPException(status_code=404, detail="Class not found")

        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role == 'admin':
            pass  # 管理员有权访问
        elif requester_role == 'teacher':
            if requester.managed_class_id != class_id:
                raise HTTPException(status_code=403, detail="Permission denied")
        else:
            raise HTTPException(status_code=403, detail="Permission denied")

        # 获取该班级学生 id 列表
        students = db.query(User.id).filter(User.class_id == class_id).all()
        student_ids = [s[0] for s in students]

        q = db.query(Grade).filter(Grade.student_id.in_(student_ids))
        if subject:
            q = q.filter(Grade.subject == subject)
        if semester:
            q = q.filter(Grade.semester == semester)

        total = q.count()
        page = max(1, int(page))
        size = min(200, max(1, int(size)))
        rows = q.order_by(Grade.student_id.asc(), Grade.subject.asc()).offset((page-1)*size).limit(size).all()
        items = [{"id": r.id, "student_id": r.student_id, "subject": r.subject, "score": r.score, "semester": r.semester, "teacher_id": r.teacher_id} for r in rows]
        return {"status":"success", "total": total, "page": page, "size": size, "items": items}
    finally:
        db.close()

@app.get("/mcp/class/{class_identifier}/students")
def get_students_in_class(class_identifier: str, requester_id: str = Query(...)):
    """获取班级学生列表（仅限教师/管理员）"""
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        class_id = get_class_id_from_class_code(db, class_identifier) or int(class_identifier)
        if not class_id:
            raise HTTPException(status_code=404, detail="Class not found")

        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role not in ['teacher', 'admin']:
            raise HTTPException(status_code=403, detail="Permission denied")

        if requester_role == 'teacher' and requester.managed_class_id != class_id:
            raise HTTPException(status_code=403, detail="Permission denied: cannot access students of another class")

        students = db.query(User).filter(User.class_id == class_id, User.role == UserRole.student).all()
        items = [{"id": s.id, "username": s.username} for s in students]
        return {"status": "success", "students": items}
    finally:
        db.close()

@app.put("/mcp/grades/{grade_id}")
def update_grade(grade_id: int, body: dict, requester_id: str = Query(...)):
    """修改成绩（仅限教师）"""
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        # 权限检查：必须是教师
        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role != 'teacher':
            raise HTTPException(status_code=403, detail="Permission denied: only teacher can update grades")

        # 查找成绩记录
        grade = db.get(Grade, int(grade_id))
        if not grade:
            raise HTTPException(status_code=404, detail="Grade not found")

        # 权限：教师只能修改自己录入的成绩
        if grade.teacher_id != requester_id_internal:
            raise HTTPException(status_code=403, detail="Permission denied: cannot update grade created by another teacher")

        # 更新字段
        if 'subject' in body:
            grade.subject = body['subject']
        if 'score' in body:
            grade.score = int(body['score'])
        if 'semester' in body:
            grade.semester = body['semester']

        db.commit()
        db.refresh(grade)
        return {"status": "success", "grade_id": grade.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.delete("/mcp/grades/{grade_id}")
def delete_grade(grade_id: int, requester_id: str = Query(...)):
    """删除成绩（仅限教师）"""
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        # 权限检查：必须是教师
        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role != 'teacher':
            raise HTTPException(status_code=403, detail="Permission denied: only teacher can delete grades")

        # 查找成绩记录
        grade = db.get(Grade, int(grade_id))
        if not grade:
            raise HTTPException(status_code=404, detail="Grade not found")

        # 权限：教师只能删除自己录入的成绩
        if grade.teacher_id != requester_id_internal:
            raise HTTPException(status_code=403, detail="Permission denied: cannot delete grade created by another teacher")

        db.delete(grade)
        db.commit()
        return {"status": "success", "deleted_grade_id": grade_id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/mcp/parent/{parent_identifier}/children")
def get_parent_children(parent_identifier: str, requester_id: str = Query(...)):
    """获取家长关联的孩子列表"""
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        parent_id = get_user_id_from_external_id(db, parent_identifier) or int(parent_identifier)
        if not parent_id:
            raise HTTPException(status_code=404, detail="Parent not found")

        # 权限检查：只有家长本人可以查看自己的孩子
        if requester_id_internal != parent_id:
            raise HTTPException(status_code=403, detail="Permission denied")

        # 查询真实的家长-孩子关联关系
        parent_user = db.get(User, parent_id)
        if not parent_user:
            raise HTTPException(status_code=404, detail="Parent not found")

        # 使用 parent_students 关联表获取真实的孩子列表
        children = db.query(User).join(
            parent_students, 
            User.id == parent_students.c.student_id
        ).filter(
            parent_students.c.parent_id == parent_id
        ).all()
        
        items = [{"id": s.id, "username": s.username} for s in children]
        return {"status": "success", "children": items}
    finally:
        db.close()

class UserProfileResponse(BaseModel):
    status: str
    user_profile: Optional[dict] = None
    detail: Optional[str] = None

class ContactItem(BaseModel):
    id: int
    name: str
    role: str

class ContactsResponse(BaseModel):
    status: str
    contacts: List[ContactItem] = []
    detail: Optional[str] = None

@app.get("/mcp/contacts", response_model=ContactsResponse)
def get_contacts(user_id: str = Query(...)):
    db = SessionLocal()
    try:
        # Get the current user
        current_user_id = get_user_id_from_external_id(db, user_id) or int(user_id)
        if not current_user_id:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_user = db.get(User, current_user_id)
        if not current_user:
            raise HTTPException(status_code=404, detail="User not found")

        contacts = []
        contact_ids = set()

        # Logic for students
        if current_user.role == UserRole.student:
            # 1. Classmates
            if current_user.class_id:
                classmates = db.query(User).filter(
                    User.class_id == current_user.class_id,
                    User.role == UserRole.student,
                    User.id != current_user.id
                ).all()
                for user in classmates:
                    if user.id not in contact_ids:
                        contacts.append({"id": user.id, "name": f"{user.username} (同学)", "role": "student"})
                        contact_ids.add(user.id)

            # 2. Parents
            parent_ids = db.query(parent_students.c.parent_id).filter(parent_students.c.student_id == current_user.id).all()
            parent_ids_list = [pid[0] for pid in parent_ids]
            if parent_ids_list:
                parents = db.query(User).filter(User.id.in_(parent_ids_list)).all()
                for user in parents:
                     if user.id not in contact_ids:
                        contacts.append({"id": user.id, "name": f"{current_user.username}家长", "role": "parent"})
                        contact_ids.add(user.id)

            # 3. Teachers
            if current_user.class_id:
                teachers = db.query(User).filter(
                    User.role == UserRole.teacher,
                    User.managed_class_id == current_user.class_id
                ).all()
                for user in teachers:
                    if user.id not in contact_ids:
                        contacts.append({"id": user.id, "name": f"{user.username} (老师)", "role": "teacher"})
                        contact_ids.add(user.id)
        
        # Logic for teachers
        elif current_user.role == UserRole.teacher:
            if current_user.managed_class_id:
                students = db.query(User).filter(
                    User.class_id == current_user.managed_class_id,
                    User.role == UserRole.student
                ).all()
                for user in students:
                    if user.id not in contact_ids:
                        contacts.append({"id": user.id, "name": user.username, "role": "student"})
                        contact_ids.add(user.id)

        # Logic for parents
        elif current_user.role == UserRole.parent:
            children_ids = db.query(parent_students.c.student_id).filter(parent_students.c.parent_id == current_user.id).all()
            children_ids_list = [cid[0] for cid in children_ids]
            if children_ids_list:
                children = db.query(User).filter(User.id.in_(children_ids_list)).all()
                for user in children:
                    if user.id not in contact_ids:
                        contacts.append({"id": user.id, "name": user.username, "role": "student"})
                        contact_ids.add(user.id)

        return ContactsResponse(status="success", contacts=contacts)

    except Exception as e:
        return ContactsResponse(status="error", detail=str(e))
    finally:
        db.close()

@app.get("/mcp/user/profile", response_model=UserProfileResponse)
def get_user_profile(requester_id: str = Query(..., description="requester user id")):
    db = SessionLocal()
    try:
        user_id = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile_data = {}
        enrollment_year = None
        
        if user.role == UserRole.parent:
            child = user.children[0] if user.children else None
            if child:
                profile_data["name"] = f"{child.username}家长"
                profile_data["external_id"] = None # Parents don't have this
                profile_data["class_name"] = child.class_.name if hasattr(child, 'class_') and child.class_ else None
                profile_data["school_name"] = child.school.name if hasattr(child, 'school') and child.school else None
                
                # Extract enrollment year from child's class_code
                if hasattr(child, 'class_') and child.class_ and child.class_.class_code and len(child.class_.class_code) >= 4:
                    try:
                        year = int(child.class_.class_code[:4])
                        enrollment_year = str(year)
                    except ValueError:
                        pass
            else:
                profile_data["name"] = f"{user.username} (家长)"
        else:
            profile_data["name"] = user.username
            profile_data["external_id"] = user.external_id
            
            # For teachers, get class name from managed_class_id
            if user.role == UserRole.teacher:
                if user.managed_class_id:
                    managed_class = db.get(Class, user.managed_class_id)
                    profile_data["class_name"] = managed_class.name if managed_class else None
                    # Extract enrollment year from managed_class's class_code
                    if managed_class and managed_class.class_code and len(managed_class.class_code) >= 4:
                        try:
                            year = int(managed_class.class_code[:4])
                            enrollment_year = str(year)
                        except ValueError:
                            pass
                else:
                    profile_data["class_name"] = None
            else:
                # For students, get class name from class_id
                profile_data["class_name"] = user.class_.name if hasattr(user, 'class_') and user.class_ else None
                # Extract enrollment year from user's class_code
                if hasattr(user, 'class_') and user.class_ and user.class_.class_code and len(user.class_.class_code) >= 4:
                    try:
                        year = int(user.class_.class_code[:4])
                        enrollment_year = str(year)
                    except ValueError:
                        pass
            
            profile_data["school_name"] = user.school.name if hasattr(user, 'school') and user.school else None

        profile_data["enrollment_year"] = enrollment_year

        return UserProfileResponse(status="success", user_profile=profile_data)
    except Exception as e:
        return UserProfileResponse(status="error", detail=str(e))
    finally:
        db.close()

@app.get("/mcp/user/{user_identifier}")
def get_user_info(user_identifier: str):
    """返回 user 基本信息（id, username, role, class_id 等），供前端登录校验使用。"""
    db = SessionLocal()
    try:
        user_id = get_user_id_from_external_id(db, user_identifier) or int(user_identifier)
        if not user_id:
            return {"status": "error", "detail": "user not found", "user": None}
        
        u = db.get(User, user_id)
        if not u:
            return {"status": "error", "detail": "user not found", "user": None}
        # 将 role、username、id、class_id 等信息返回（role 可能是 Enum 或 str）
        return {
            "status": "success",
            "user": {
                "id": u.id,
                "username": getattr(u, "username", None),
                "role": getattr(u, "role", None),
                "class_id": getattr(u, "class_id", None),
                "managed_class_id": getattr(u, "managed_class_id", None)
            }
        }
    finally:
        db.close()

@app.put("/mcp/user/profile")
def update_user_profile(requester_id: str = Query(...), profile_data: dict = {}):
    db = SessionLocal()
    try:
        user_id = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target_user = user
        if user.role == UserRole.parent:
            child = user.children[0] if user.children else None
            if child:
                target_user = child
            else:
                raise HTTPException(status_code=404, detail="Child not found for parent")

        if 'name' in profile_data:
            if user.role == UserRole.parent:
                name_to_set = profile_data['name']
                if name_to_set.endswith('家长'):
                    name_to_set = name_to_set[:-2]
                target_user.username = name_to_set
            else:
                target_user.username = profile_data['name']

        if 'external_id' in profile_data and user.role != UserRole.parent:
            target_user.external_id = profile_data['external_id']
        
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/mcp/admin/stats")
def admin_stats(requester_id: str = Query(..., description="requester user id for permission check")):
    """
    返回管理面板的简要统计：
      - pending_outgoing: 待发送队列（未 delivered）的数量（仅 admin 可见）
      - unconfirmed_memos: 今日未确认的 memo 数（仅 admin 可见）
      - daily_quote: dict 包含 { total_active, scheduled_now: [...], enqueued_today }（admin 与 teacher 可见）
    """
    db = SessionLocal()
    try:
        requester_id_internal = get_user_id_from_external_id(db, requester_id) or int(requester_id)
        if not requester_id_internal:
            raise HTTPException(status_code=404, detail="Requester not found")
        requester = db.get(User, requester_id_internal)
        if not requester:
            raise HTTPException(status_code=403, detail="requester not found")

        rrole = getattr(requester, "role", None)

        # 直接比较 Enum，更健壮
        is_admin = (rrole == UserRole.admin)
        is_teacher = (rrole == UserRole.teacher)

        result = {
            "status": "success",
            "pending_outgoing": None,
            "unconfirmed_memos": None,
            "daily_quote": None
        }

        # Admin-only metrics
        if is_admin:
            try:
                pending = db.query(OutgoingQueue).filter(OutgoingQueue.delivered == False).count()
            except Exception:
                pending = 0
            # 今日未确认 memo（按 remind_date == today）
            today = datetime.now(TZ).date()
            try:
                memo_cnt = db.query(Memo).filter(Memo.remind_date == today).count()
            except Exception:
                memo_cnt = 0

            result["pending_outgoing"] = int(pending)
            result["unconfirmed_memos"] = int(memo_cnt)

        # daily quote info for admin+teacher
        if is_admin or is_teacher:
            now_sh = datetime.now(TZ)
            hm = now_sh.strftime("%H:%M")
            # 总 active
            try:
                total_active = db.query(DailyQuote).filter(DailyQuote.active == True).count()
            except Exception:
                total_active = 0

            # 当前分钟 scheduled list
            scheduled_now = []
            try:
                rows = db.query(DailyQuote).filter(DailyQuote.active == True, DailyQuote.broadcast_time == hm).all()
                for q in rows:
                    scheduled_now.append({
                        "id": q.id,
                        "class_id": q.class_id,
                        "broadcast_time": q.broadcast_time,
                        "content": q.content
                    })
            except Exception:
                scheduled_now = []

            # 检查当天已入队的 daily_quote 数量（payload 中的 date 字段）
            today_iso = now_sh.date().isoformat()
            try:
                enqueued_today = db.query(OutgoingQueue).filter(OutgoingQueue.payload.contains({
                    "type": "daily_quote",
                    "date": today_iso
                })).count()
            except Exception:
                enqueued_today = 0

            result["daily_quote"] = {
                "total_active": int(total_active),
                "scheduled_now": scheduled_now,
                "enqueued_today": int(enqueued_today)
            }

        return result

    finally:
        db.close()

@app.get("/mcp/open_windows/{class_id}", response_model=List[OpenWindowModel])
def get_open_windows(class_id: int, requester_id: int = Query(...)):
    db = SessionLocal()
    try:
        requester = db.get(User, requester_id)
        if not requester:
            raise HTTPException(status_code=403, detail="Requester not found")

        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role == 'admin':
            pass  # 管理员有权访问
        elif requester_role == 'teacher':
            if requester.managed_class_id != int(class_id):
                raise HTTPException(status_code=403, detail="Permission denied")
        else:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        windows = db.query(OpenWindow).filter(OpenWindow.class_id == class_id).all()
        return windows
    finally:
        db.close()

@app.post("/mcp/open_windows", response_model=OpenWindowModel)
def create_open_window(window: OpenWindowCreate, requester_id: int = Query(...)):
    db = SessionLocal()
    try:
        requester = db.get(User, requester_id)
        if not requester:
            raise HTTPException(status_code=403, detail="Requester not found")

        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role == 'admin':
            pass  # 管理员有权访问
        elif requester_role == 'teacher':
            if requester.managed_class_id != int(window.class_id):
                raise HTTPException(status_code=403, detail="Permission denied")
        else:
            raise HTTPException(status_code=403, detail="Permission denied")

        new_window = OpenWindow(**window.dict())
        db.add(new_window)
        db.commit()
        db.refresh(new_window)
        return new_window
    finally:
        db.close()

@app.delete("/mcp/open_windows/{window_id}", status_code=204)
def delete_open_window(window_id: int, requester_id: int = Query(...)):
    db = SessionLocal()
    try:
        requester = db.get(User, requester_id)
        if not requester:
            raise HTTPException(status_code=403, detail="Requester not found")

        window = db.get(OpenWindow, window_id)
        if not window:
            raise HTTPException(status_code=404, detail="OpenWindow not found")

        requester_role = getattr(requester.role, 'value', requester.role)
        if requester_role == 'admin':
            pass  # 管理员有权访问
        elif requester_role == 'teacher':
            if requester.managed_class_id != int(window.class_id):
                raise HTTPException(status_code=403, detail="Permission denied")
        else:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        db.delete(window)
        db.commit()
        return
    finally:
        db.close()
        
@app.get("/admin/outgoing", response_class=HTMLResponse)
def admin_outgoing_page():
    html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Outgoing Queue 管理</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
</head>
<body class="bg-light">
  <div class="container py-4">
    <h3>Outgoing Queue 管理</h3>
    <p class="text-muted">注意：仅用于本地调试。实际部署请接入登录/权限。</p>

    <div class="row g-2 align-items-end">
      <div class="col-md-2">
        <label class="form-label">requester_id（必填，用于权限）</label>
        <input id="requester_id" class="form-control" type="number" value="" />
      </div>
      <div class="col-md-2">
        <label class="form-label">target_user_id（可选）</label>
        <input id="target_user_id" class="form-control" type="number" />
      </div>
      <div class="col-md-2">
        <label class="form-label">delivered（可选 0/1）</label>
        <input id="delivered" class="form-control" type="number" min="0" max="1" />
      </div>
      <div class="col-md-2">
        <label class="form-label">priority（可选）</label>
        <input id="priority" class="form-control" type="text" placeholder="urgent/normal" />
      </div>
      <div class="col-md-2">
        <label class="form-label">page</label>
        <input id="page" class="form-control" type="number" value="1" min="1" />
      </div>
      <div class="col-md-2">
        <label class="form-label">size</label>
        <input id="size" class="form-control" type="number" value="20" min="1" max="200" />
      </div>
    </div>

    <div class="mt-3">
      <button id="loadBtn" class="btn btn-primary btn-sm">加载</button>
      <button id="refreshBtn" class="btn btn-outline-secondary btn-sm">刷新</button>
      <button id="ackSelectedBtn" class="btn btn-success btn-sm">确认选中 (ack)</button>
      <button id="markDeliveredBtn" class="btn btn-info btn-sm">标记已投递</button>
      <button id="deleteSelectedBtn" class="btn btn-danger btn-sm">删除选中</button>
    </div>

    <div class="mt-3">
      <div id="alertArea"></div>
      <table class="table table-sm table-hover bg-white" id="resultTable">
        <thead>
          <tr>
            <th><input id="selectAll" type="checkbox"></th>
            <th>ID</th>
            <th>target_user</th>
            <th>priority</th>
            <th>delivered</th>
            <th>created_at</th>
            <th>deliver_after</th>
            <th>payload</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <nav>
      <ul class="pagination" id="pager"></ul>
    </nav>
  </div>

<script>
const $ = (id)=>document.getElementById(id);

function showAlert(msg, kind='info') {
  const area = $('alertArea');
  area.innerHTML = `<div class="alert alert-${kind} alert-sm">${msg}</div>`;
  setTimeout(()=>area.innerHTML='', 4000);
}

async function loadPage() {
  const requester_id = $('requester_id').value;
  if(!requester_id){ showAlert('requester_id 必填','warning'); return; }
  const target_user_id = $('target_user_id').value;
  const delivered = $('delivered').value;
  const priority = $('priority').value;
  const page = $('page').value || 1;
  const size = $('size').value || 20;

  let url = `/mcp/outgoing/list?requester_id=${encodeURIComponent(requester_id)}&page=${page}&size=${size}`;
  if(target_user_id) url += `&target_user_id=${encodeURIComponent(target_user_id)}`;
  if(delivered !== '') url += `&delivered=${encodeURIComponent(delivered)}`;
  if(priority) url += `&priority=${encodeURIComponent(priority)}`;

  try {
    const res = await fetch(url);
    if(!res.ok){
      const txt = await res.text();
      showAlert('请求失败: ' + res.status + ' ' + txt, 'danger');
      return;
    }
    const data = await res.json();
    if(data.status !== 'success'){ showAlert('接口返回: '+ JSON.stringify(data),'warning'); return; }
    renderTable(data);
  } catch (e) {
    showAlert('请求异常: ' + e, 'danger');
  }
}

function renderTable(data){
  const tbody = document.querySelector('#resultTable tbody');
  tbody.innerHTML = '';
  data.items.forEach(it=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input class="rowCheck" data-id="${it.id}" type="checkbox"></td>
      <td>${it.id}</td>
      <td>${it.target_user_id}</td>
      <td>${it.priority}</td>
      <td>${it.delivered ? '✔' : ''}</td>
      <td>${it.created_at || ''}</td>
      <td>${it.deliver_after || ''}</td>
      <td><pre style="white-space:pre-wrap;max-width:400px">${escapeHtml(JSON.stringify(it.payload, null, 2))}</pre></td>
    `;
    tbody.appendChild(tr);
  });

  // pager
  const pager = $('pager');
  pager.innerHTML = '';
  const total = data.total || 0;
  const page = data.page || 1;
  const size = data.size || 20;
  const pages = Math.max(1, Math.ceil(total/size));
  for(let p=1;p<=pages && p<=20;p++){
    const li = document.createElement('li');
    li.className = 'page-item ' + (p==page?'active':'');
    li.innerHTML = `<a class="page-link" href="#">${p}</a>`;
    li.onclick = (ev)=>{ ev.preventDefault(); $('page').value = p; loadPage(); };
    pager.appendChild(li);
  }
}

function escapeHtml(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function getSelectedIds(){
  const chks = Array.from(document.querySelectorAll('.rowCheck:checked'));
  return chks.map(c=>parseInt(c.dataset.id));
}

async function postJson(url, body){
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  return res;
}

$('loadBtn').onclick = loadPage;
$('refreshBtn').onclick = loadPage;
$('selectAll').onclick = ()=>{
  const checked = $('selectAll').checked;
  document.querySelectorAll('.rowCheck').forEach(c=>c.checked = checked);
};

$('ackSelectedBtn').onclick = async ()=>{
  const ids = getSelectedIds();
  if(ids.length===0){ showAlert('请选择要确认的条目','warning'); return; }
  const requester_id = $('requester_id').value;
  const res = await postJson('/mcp/ack', {ids: ids, user_id: requester_id});
  if(res.ok){ showAlert('ack 成功','success'); loadPage(); } else { showAlert('ack 失败','danger'); }
};

$('markDeliveredBtn').onclick = async ()=>{
  const ids = getSelectedIds();
  if(ids.length===0){ showAlert('请选择要标记的条目','warning'); return; }
  const res = await postJson('/mcp/outgoing/mark_delivered', {ids: ids});
  if(res.ok){ showAlert('标记成功','success'); loadPage(); } else { showAlert('标记失败','danger'); }
};

$('deleteSelectedBtn').onclick = async ()=>{
  const ids = getSelectedIds();
  if(ids.length===0){ showAlert('请选择要删除的条目','warning'); return; }
  if(!confirm('确定删除选中项吗？')) return;
  const res = await postJson('/mcp/outgoing/delete', {ids: ids});
  if(res.ok){ showAlert('删除成功','success'); loadPage(); } else { showAlert('删除失败','danger'); }
};

// auto load if requester_id present in querystring
(function initFromQuery(){
  const params = new URLSearchParams(location.search);
  if(params.get('requester_id')) $('requester_id').value = params.get('requester_id');
  if(params.get('target_user_id')) $('target_user_id').value = params.get('target_user_id');
  if(params.get('delivered')) $('delivered').value = params.get('delivered');
  if(params.get('page')) $('page').value = params.get('page');
  if(params.get('size')) $('size').value = params.get('size');
})();
</script>

</body>
</html>
    """
    return HTMLResponse(content=html)

# -------------------- 登录和注册接口 --------------------
class LoginRequest(BaseModel):
    external_id: str
    password: str

class RegisterRequest(BaseModel):
    external_id: str
    username: str
    password: str
    confirm_password: str
    role: UserRole
    class_code: Optional[str] = None
    school_code: Optional[str] = None

class LoginResponse(BaseModel):
    status: str
    user_id: Optional[int] = None
    external_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    class_id: Optional[int] = None
    managed_class_id: Optional[int] = None
    detail: Optional[str] = None

class RegisterResponse(BaseModel):
    status: str
    user_id: Optional[int] = None
    detail: Optional[str] = None

@app.post("/mcp/auth/login", response_model=LoginResponse)
def login(login_request: LoginRequest):
    """使用 external_id 和密码进行登录"""
    db = SessionLocal()
    try:
        # 通过 external_id 查找用户
        user = db.query(User).filter(User.external_id == login_request.external_id).first()
        if not user:
            return LoginResponse(status="error", detail="账号不存在")
        
        # 验证密码
        if not check_password_hash(user.password_hash, login_request.password):
            return LoginResponse(status="error", detail="密码错误")
        
        # 返回用户信息
        return LoginResponse(
            status="success",
            user_id=user.id,
            external_id=user.external_id,
            username=user.username,
            role=user.role.value,
            class_id=user.class_id,
            managed_class_id=user.managed_class_id,
            detail="登录成功"
        )
    except Exception as e:
        return LoginResponse(status="error", detail=str(e))
    finally:
        db.close()

@app.post("/mcp/auth/register", response_model=RegisterResponse)
def register(register_request: RegisterRequest):
    """用户注册接口"""
    db = SessionLocal()
    try:
        # 验证密码确认
        if register_request.password != register_request.confirm_password:
            return RegisterResponse(status="error", detail="密码和确认密码不一致")
        
        # 检查 external_id 是否已存在
        existing_user = db.query(User).filter(User.external_id == register_request.external_id).first()
        if existing_user:
            return RegisterResponse(status="error", detail="该账号已存在")
        
        # 检查 username 是否已存在
        existing_username = db.query(User).filter(User.username == register_request.username).first()
        if existing_username:
            return RegisterResponse(status="error", detail="该用户名已存在")
        
        # 处理班级代号映射
        class_id = None
        if register_request.class_code:
            class_obj = db.query(Class).filter(Class.class_code == register_request.class_code).first()
            if class_obj:
                class_id = class_obj.id
            else:
                return RegisterResponse(status="error", detail=f"班级代号 '{register_request.class_code}' 不存在")
        
        # 处理学校代号映射
        school_id = None
        if register_request.school_code:
            school_obj = db.query(School).filter(School.code == register_request.school_code).first()
            if school_obj:
                school_id = school_obj.id
            else:
                return RegisterResponse(status="error", detail=f"学校代号 '{register_request.school_code}' 不存在")
        
        # 根据角色设置相应的班级字段
        if register_request.role == UserRole.student or register_request.role == UserRole.parent:
            # 学生和家长设置 class_id
            class_field = "class_id"
        elif register_request.role == UserRole.teacher:
            # 教师设置 managed_class_id
            class_field = "managed_class_id"
        else:
            # 其他角色不设置班级字段
            class_field = None
        
        # 创建新用户
        user_data = {
            "external_id": register_request.external_id,
            "username": register_request.username,
            "password_hash": generate_password_hash(register_request.password),
            "role": register_request.role,
            "is_active": True,
            "school_id": school_id
        }
        
        # 设置相应的班级字段
        if class_field and class_id:
            user_data[class_field] = class_id
        
        new_user = User(**user_data)
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return RegisterResponse(
            status="success",
            user_id=new_user.id,
            detail="注册成功"
        )
    except Exception as e:
        db.rollback()
        return RegisterResponse(status="error", detail=str(e))
    finally:
        db.close()

class ParentChildSelectionRequest(BaseModel):
    parent_id: str
    student_id: str

class ParentChildSelectionResponse(BaseModel):
    status: str
    detail: Optional[str] = None

@app.post("/mcp/parent/select_child", response_model=ParentChildSelectionResponse)
def parent_select_child(selection_request: ParentChildSelectionRequest):
    """家长选择孩子接口"""
    db = SessionLocal()
    try:
        parent_id = get_user_id_from_external_id(db, selection_request.parent_id) or int(selection_request.parent_id)
        student_id = get_user_id_from_external_id(db, selection_request.student_id) or int(selection_request.student_id)
        
        if not parent_id or not student_id:
            return ParentChildSelectionResponse(status="error", detail="家长或学生不存在")
        
        # 检查家长角色
        parent = db.get(User, parent_id)
        if not parent or parent.role != UserRole.parent:
            return ParentChildSelectionResponse(status="error", detail="用户不是家长角色")
        
        # 检查学生角色
        student = db.get(User, student_id)
        if not student or student.role != UserRole.student:
            return ParentChildSelectionResponse(status="error", detail="选择的对象不是学生")
        
        # 检查学生是否在同一班级
        if parent.class_id != student.class_id:
            return ParentChildSelectionResponse(status="error", detail="学生不在您的班级中")
        
        # 检查是否已经关联
        existing_relation = db.query(parent_students).filter(
            parent_students.c.parent_id == parent_id,
            parent_students.c.student_id == student_id
        ).first()
        
        if existing_relation:
            return ParentChildSelectionResponse(status="error", detail="已经关联过该学生")
        
        # 建立关联
        db.execute(parent_students.insert().values(
            parent_id=parent_id,
            student_id=student_id
        ))
        db.commit()
        
        return ParentChildSelectionResponse(status="success", detail="孩子选择成功")
    except Exception as e:
        db.rollback()
        return ParentChildSelectionResponse(status="error", detail=str(e))
    finally:
        db.close()

class AvailableStudentsResponse(BaseModel):
    status: str
    students: List[dict] = []
    detail: Optional[str] = None

@app.get("/mcp/parent/available_students", response_model=AvailableStudentsResponse)
def get_available_students(parent_id: str = Query(...)):
    """获取家长可选择的同班学生列表"""
    db = SessionLocal()
    try:
        parent_user_id = get_user_id_from_external_id(db, parent_id) or int(parent_id)
        if not parent_user_id:
            return AvailableStudentsResponse(status="error", detail="家长不存在")
        
        parent_user = db.get(User, parent_user_id)
        if not parent_user or parent_user.role != UserRole.parent:
            return AvailableStudentsResponse(status="error", detail="用户不是家长角色")
        
        # 获取同班级的所有学生
        students = db.query(User).filter(
            User.class_id == parent_user.class_id,
            User.role == UserRole.student
        ).all()
        
        # 获取已经关联的学生ID
        related_student_ids = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == parent_user_id
        ).all()
        related_ids = [r[0] for r in related_student_ids]
        
        # 过滤掉已经关联的学生
        available_students = []
        for student in students:
            if student.id not in related_ids:
                available_students.append({
                    "id": student.id,
                    "external_id": student.external_id,
                    "username": student.username,
                    "class_id": student.class_id
                })
        
        return AvailableStudentsResponse(status="success", students=available_students)
    except Exception as e:
        return AvailableStudentsResponse(status="error", detail=str(e))
    finally:
        db.close()

class ParentStatusResponse(BaseModel):
    status: str
    has_selected_child: bool = False
    detail: Optional[str] = None

@app.get("/mcp/parent/status", response_model=ParentStatusResponse)
def get_parent_status(parent_id: str = Query(...)):
    """检查家长是否已经选择了孩子"""
    db = SessionLocal()
    try:
        parent_user_id = get_user_id_from_external_id(db, parent_id) or int(parent_id)
        if not parent_user_id:
            return ParentStatusResponse(status="error", detail="家长不存在")
        
        parent_user = db.get(User, parent_user_id)
        if not parent_user or parent_user.role != UserRole.parent:
            return ParentStatusResponse(status="error", detail="用户不是家长角色")
        
        # 检查是否有关联的孩子
        child_count = db.query(parent_students).filter(
            parent_students.c.parent_id == parent_user_id
        ).count()
        
        has_selected_child = child_count > 0
        
        return ParentStatusResponse(
            status="success", 
            has_selected_child=has_selected_child,
            detail="已选择孩子" if has_selected_child else "未选择孩子"
        )
    except Exception as e:
        return ParentStatusResponse(status="error", detail=str(e))
    finally:
        db.close()

# -------------------- 启动用 --------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mcp.app:app", host="0.0.0.0", port=8000, reload=True)
