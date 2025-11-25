# shared/schemas.py
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional, List, Literal

# 导入 NoticeType 枚举
from shared.models import NoticeType  

# 基础命令模型
class Command(BaseModel):
    command: str
    user_id: str
    role: str
    timestamp: datetime
    context: dict

# leave_message 用的上下文
class LeaveMessageContext(BaseModel):
    receiver_id: str
    content: str
    audio_url: Optional[str] = None
    priority: Optional[Literal["normal", "urgent"]] = "normal"

class LeaveMessageCommand(Command):
    context: LeaveMessageContext

class LeaveMessageResponse(BaseModel):
    status: str                 # "success" or "error"
    message_id: Optional[int]
    detail: Optional[str]

# get_messages 命令与响应结构
class GetMessagesCommand(Command):
    pass

class MessageItem(BaseModel):
    id: int
    sender_id: str
    content: str
    audio_url: Optional[str]
    priority: str
    timestamp: datetime

class GetMessagesResponse(BaseModel):
    status: str                 # "success" or "error"
    messages: List[MessageItem]
    detail: Optional[str]

# post_notice 命令与响应结构
class PostNoticeContext(BaseModel):
    content: str
    priority: Literal["normal", "urgent"]
    target_class: Optional[str] = None
    target_role: Optional[str] = None

class PostNoticeCommand(Command):
    # 强制 command 为 "post_notice"
    command: Literal["post_notice"]
    context: PostNoticeContext

class PostNoticeResponse(BaseModel):
    status: str
    notice_id: Optional[int] = None
    detail: Optional[str] = None

class PlayAudioContext(BaseModel):
    message_id: int

class PlayAudioCommand(Command):
    command: Literal["play_audio"]
    context: PlayAudioContext

class PlayAudioResponse(BaseModel):
    status: str               # "success" / "error"
    audio_url: Optional[str]  # 成功时返回语音地址
    detail: Optional[str]     # 错误信息

# 学生添加备忘录时的上下文
class AddMemoContext(BaseModel):
    content: str
    remind_date: datetime  # 你也可以用 date，根据需求调整

# add_memo 命令
class AddMemoCommand(Command):
    command: Literal["add_memo"]
    context: AddMemoContext

# add_memo 的响应
class AddMemoResponse(BaseModel):
    status: str               # "success" / "error"
    memo_id: Optional[int]    # 新增备忘的 ID
    detail: Optional[str]     # 错误信息

# 学生确认完成备忘时的上下文
class ConfirmMemoContext(BaseModel):
    memo_id: int

# confirm_memo 命令
class ConfirmMemoCommand(Command):
    command: Literal["confirm_memo"]
    context: ConfirmMemoContext

# confirm_memo 的响应
class ConfirmMemoResponse(BaseModel):
    status: str               # "success" / "error"
    detail: Optional[str]     # 错误信息，成功时为 None
    
# 新增：今日备忘命令（无具体 context，仅空对象）
class GetTodayMemoCommand(Command):
    command: Literal["get_today_memo"]
    context: dict = {}   # 空上下文

# 单条备忘结构
class MemoItem(BaseModel):
    id: int
    content: str
    remind_date: datetime

# 今日备忘响应
class GetTodayMemoResponse(BaseModel):
    status: str               # "success" or "error"
    memos: List[MemoItem]     # 待提醒的备忘列表
    detail: Optional[str]     # 错误信息