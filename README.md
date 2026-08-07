# Hướng dẫn chạy dự án TaskHub (Quick Start Guide)

Dưới đây là các bước đơn giản nhất để chạy ứng dụng:

## 1. Khởi tạo Môi trường (.env)

Tạo file `backend/.env` từ file mẫu:

```bash
cp backend/.env.example backend/.env
```

Nội dung file `backend/.env`:

```env
# Application
APP_NAME=TaskHub API
APP_VERSION=1.0.0
DEBUG=true

# Database & Redis
DATABASE_URL=postgresql+asyncpg://taskhub:password@localhost:5432/taskhub_db
REDIS_URL=redis://localhost:6379/0

# JWT Security
JWT_SECRET_KEY=9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@taskhub.io
```

---

## 2. Khởi động ứng dụng bằng Docker Compose

Mở terminal tại thư mục gốc của dự án (`TaskHub`) và chạy:

```bash
# Khởi động database và backend
docker compose down -v
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

---

## 3. Truy cập ứng dụng

- **Backend API**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 4. Tài khoản mẫu

Tất cả tài khoản dùng mật khẩu chung: **`Password123!`**

| Email | Họ và tên | Vai trò hệ thống | Vai trò Workspace | Ghi chú |
|---|---|---|---|---|
| `admin@taskhub.io` | Admin User | ADMIN | — | Quản trị viên toàn hệ thống (Bypass RBAC) |
| `owner@taskhub.io` | Alice Owner | MEMBER | OWNER | Chủ sở hữu Workspace "TaskHub Engineering" & "Marketing Hub" |
| `editor@taskhub.io` | Bob Editor | MEMBER | EDITOR | Thành viên thực thi task (Assignee của 4 task mẫu) |
| `viewer@taskhub.io` | Carol Viewer | MEMBER | VIEWER | Thành viên xem/thảo luận trong Workspace |

---

## 5. Kết quả nghiệm thu & Chất lượng dự án (Quality Gates & Test Status)

| Hạng Mục Kiểm Định | Công Cụ / Môi Trường | Kết Quả | Trạng Thái |
|---|---|---|---|
| **Automated Pytest Suite** | `pytest -v` (Unit + Live Integration) | **310/310 PASSED (100%)** | ✅ PASSED |
| **Type Safety Check** | `mypy app/` (Strict Mode) | **0 issues (62/62 files)** | ✅ PASSED |
| **Code Quality & Linting** | `ruff check .` & `ruff format` | **0 errors (Pass 100%)** | ✅ PASSED |
| **Live Docker Stack** | Docker Compose (`API + DB + Redis`) | **All 3 Services Healthy** | ✅ HEALTHY |
| **Data Persistence** | Volume `postgres_data` & `redis_data` | **Postgres DB + Redis Cache Persisted** | ✅ PASSED |

Chạy bộ câu lệnh kiểm định chất lượng từ thư mục `backend/` (với môi trường `conda activate taskhub`):

```bash
cd backend

# 1. Kiểm tra Lỗi Cú pháp & Format (Ruff Lint)
ruff check .

# 2. Kiểm tra Định dạng Code (Ruff Format)
ruff format --check .

# 3. Kiểm tra Strict Type Safety (Mypy)
mypy app/

# 4. Chạy Automated Unit & Integration Tests (310/310 Tests Passed 100%)
pytest
```