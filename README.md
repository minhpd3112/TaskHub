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