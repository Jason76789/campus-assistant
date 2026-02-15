# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Campus Assistant is an educational platform built on the MCP (Model Context Protocol) architecture. It provides campus services centered around the "小智" (Xiaozhi) dialogue robot (ESP32 hardware) for students, with web and mobile interfaces for teachers, parents, and administrators.

**Student Terminal**: 小智 dialogue robot (ESP32) accessing services via MCP protocol
**Other Roles (Teacher/Parent/Admin)**: Web and mobile applications

## Architecture

### Component Relationships

```
┌─────────────────────────────────────────────────────────────────────┐
│                         小智 Dialogue Robot (ESP32)                │
│                            (Student Terminal)                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ JSON-RPC 2.0
                                ▼
                    ┌──────────────────────┐
                    │   MCP Tools Layer    │
                    │  (FastMCP + stdio)   │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                              │
                ▼                              ▼
        ┌───────────────┐            ┌─────────────────┐
        │ Remote MCP    │            │  FastAPI Backend │
        │ Broker        │◄───────────│  (Local API)     │
        │ (xiaozhi.me)  │            └────────┬────────┘
        └───────────────┘                     │
                                             ▼
                                      ┌───────────────┐
                                      │   MySQL DB    │
                                      └───────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │              Web Frontend (Testing Interface)           │
    │                  React + Vite + Ant Design              │
    └─────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                         FastAPI Backend

    ┌─────────────────────────────────────────────────────────┐
    │           Mobile App (Capacitor for Teacher/Parent)    │
    └─────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                         FastAPI Backend
```

### Key Directories

- `mcp/` - MCP implementation, FastMCP server, student tools, WebSocket bridge (`mcp_pipe.py`)
- `web/` - React 19 + TypeScript + Vite + Ant Design **testing interface** (not primary student UI)
- `mobile/` - Capacitor mobile app for **teacher/parent/admin** roles (basic structure)
- `shared/` - Shared SQLAlchemy models and schemas
- `docs/` - Project documentation

## Common Development Commands

### Backend (MCP Service)
```bash
# Start FastAPI MCP server with hot reload
cd mcp
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Or use the provided Python script
python start_backend_service.py
```

### Web Frontend (Testing Interface)
```bash
cd web
npm run dev          # Development server (Vite)
npm run build        # Production build (tsc + vite build)
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

### MCP Tools (小智 Robot Integration)
```bash
# Connect to remote MCP broker for 小智 dialogue robot
export MCP_ENDPOINT="wss://api.xiaozhi.me/mcp/?token=YOUR_TOKEN"
export MCP_BASE_URL="http://127.0.0.1:8000"
python mcp/mcp_pipe.py mcp/student_tools.py
```

### Mobile App (Teacher/Parent/Admin)
```bash
cd web
npm run cap:sync     # Sync web app to Android
npm run cap:build    # Build and sync in one step
npm run cap:open     # Open Android Studio
```

## Data Model Architecture

### Database Schema (MySQL with SQLAlchemy ORM)

The schema uses a dual-model pattern for class management:

1. **Legacy `Class` model** - Simple class definitions (`shared/models.py:123-157`)
   - Used for basic class tracking
   - References via `User.class_id` and `User.managed_class_id`

2. **New `ClassInstance` model** - Per-school-year instances (`shared/models.py:160-183`)
   - Supports temporal class management across school years
   - References via `Enrollment` table for student history
   - Preferred for new features

### Key Models and Relationships

- **User** (`shared/models.py:59-120`) - Multi-role (student/teacher/parent/admin) with external_id mapping
  - `external_id` maps business IDs (student/employee numbers) to internal database IDs
  - `school_id` links to schools
  - `class_id` (legacy) / `managed_class_id` for class management
  - `is_active` and `graduation_date` for lifecycle management

- **parent_students** association table (`shared/models.py:16-23`) - Many-to-many parent-child relationships

- **Message** (`shared/models.py:201-219`) - Direct messages and notices with `is_notice`, `target_class`, `target_role` flags

- **Grade** (`shared/models.py:222-237`) - Student grades with optional `class_instance_id` for new model compatibility

- **Memo** (`shared/models.py:240-251`) - Student reminders with `status_json` (MySQL JSON column)

- **DailyQuote** (`shared/models.py:266-286`) - Daily quotes (鸡汤) with voice playback for 小智 robot

- **OutgoingQueue** (`shared/models.py:307-317`) - Notification queue for message delivery to 小智 devices

### External ID Mapping

The system maps external business identifiers (student numbers, employee IDs) to internal database IDs:
- Use `get_user_id_from_external_id()` helper (`mcp/db.py`)
- Use `get_class_id_from_class_code()` helper (`mcp/db.py`)

## MCP Protocol

### Command Pattern

The backend accepts POST requests to `/mcp/command` with JSON bodies:

```json
{
  "command": "add_memo",
  "user_id": "external_id",
  "role": "student|teacher|parent|admin",
  "timestamp": "2025-10-01T12:00:00+08:00",
  "context": { ...command-specific data... },
  "idempotency_key": "uuid"
}
```

Supported commands (see `shared/schemas.py`):
- `leave_message` - Send messages between users
- `get_messages` - Retrieve messages for a user
- `post_notice` - Create notices (teacher/admin)
- `play_audio` - Play audio on 小智 devices
- `add_memo` - Create student memos
- `confirm_memo` - Mark memos as confirmed
- `get_today_memo` - Get today's memos for a student

### MCP Tools Definition (小智 Robot Interface)

MCP tools are defined in `mcp/student_tools.py` using FastMCP decorators. These are the primary interface for the 小智 dialogue robot:

```python
@mcp.tool()
def get_grades(student_external_id: str, requester_external_id: str) -> Dict[str, Any]:
    """Get grades for a student with access control"""

@mcp.tool()
def get_today_memos(student_external_id: str) -> Dict[str, Any]:
    """Get today's memos for a student"""

@mcp.tool()
def add_memo(student_external_id: str, content: str, remind_date: Optional[str] = None) -> Dict[str, Any]:
    """Add a memo for a student"""

@mcp.tool()
def send_message(sender_external_id: str, receiver_external_id: str, content: str) -> Dict[str, Any]:
    """Send a message between users"""

@mcp.tool()
def get_messages(user_external_id: str) -> Dict[str, Any]:
    """Get messages for a user"""

@mcp.tool()
def poll_new_items(user_external_id: str, timeout_seconds: int = 5) -> Dict[str, Any]:
    """Poll for new messages, quotes, notifications"""
```

Tools communicate with the backend via HTTP to `BASE_URL` (configurable via `MCP_BASE_URL` env var).

### WebSocket Polling (小智 Real-time Updates)

The `/mcp/poll` endpoint supports long-polling for real-time updates on 小智 devices:

```
GET /mcp/poll?user_id=<internal_id>&timeout=5
```

Returns new messages, daily quotes (鸡汤), and other notifications within the timeout window. This is how 小智 robot receives new information (grades, memos, daily quotes, etc.).

## Role-Based Access Control & Interface

| Role | Primary Interface | Main Features |
|------|------------------|--------------|
| **Student** | 小智 Robot (ESP32) | View grades, manage memos, send messages, receive daily quotes (鸡汤) via voice |
| **Teacher** | Web / Mobile | Manage grades, post notices, manage classes, communicate with parents |
| **Parent** | Web / Mobile | View child's grades and memos, communicate with teachers |
| **Admin** | Web / Mobile | System-wide notices, user management, class management |

**Note**: Web frontend (`web/`) is primarily for testing and development, not the primary student interface.

## ESP32 Hardware Integration

The 小智 dialogue robot (ESP32) connects to the system through the MCP protocol:

1. **Device Identification**: Each ESP32 device is associated with a `student_external_id`
2. **Tool Invocation**: The robot calls MCP tools via `mcp_pipe.py` bridge to remote broker
3. **Audio Output**: `play_audio` command triggers voice playback on the device
4. **Polling**: `poll_new_items` allows the device to receive updates in real-time

See `mcp/mcp-protocol.md` for detailed hardware integration specifications (if it exists).

## Important Technical Notes

### JSON Columns in MySQL

MySQL doesn't support default values for JSON columns in DDL. Set defaults at the application level:
- `Memo.status_json` - Default to `[]` in code
- `OpenWindow.days_json` - Default to `[]` in code

### Timezone Handling

The system uses `Asia/Shanghai` timezone (`TZ = ZoneInfo("Asia/Shanghai")` in `mcp/student_tools.py:40`). All timestamps should be consistent.

### MCP Bridge Configuration

The `mcp_pipe.py` connects to remote MCP brokers for 小智 robot integration. Configure via:
- `MCP_ENDPOINT` - WebSocket URL to remote broker (xiaozhi.me)
- `MCP_BASE_URL` - Local backend API URL
- `MCP_AUTH_TOKEN` or `MCP_AUTH` - Optional authentication token

### Testing vs Production

- Use `web/` frontend for testing MCP tools and backend functionality
- Actual student interactions happen through 小智 ESP32 hardware
- Mobile app (`mobile/`) is for teacher/parent/admin roles only

## Key File Locations

- MCP server: `mcp/app.py`
- MCP tools (小智 interface): `mcp/student_tools.py`
- MCP bridge (ESP32 connection): `mcp/mcp_pipe.py`
- Database models: `shared/models.py`
- Request/Response schemas: `shared/schemas.py`
- Database helpers: `mcp/db.py`
- Web testing interface: `web/src/main.tsx`
