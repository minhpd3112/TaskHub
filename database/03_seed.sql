-- TaskHub Seed Data Script

-- 1. Users
INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at, updated_at)
VALUES 
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'admin@taskhub.io', 'Admin User', '$2b$12$PU9BlXIkzpRrXcLU1rlAjuQeAeLo2A3tnkmYyJh6Uxual2ui54LAi', 'ADMIN', true, NOW(), NOW()),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'owner@taskhub.io', 'Alice Owner', '$2b$12$PU9BlXIkzpRrXcLU1rlAjuQeAeLo2A3tnkmYyJh6Uxual2ui54LAi', 'MEMBER', true, NOW(), NOW()),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'editor@taskhub.io', 'Bob Editor', '$2b$12$PU9BlXIkzpRrXcLU1rlAjuQeAeLo2A3tnkmYyJh6Uxual2ui54LAi', 'MEMBER', true, NOW(), NOW()),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'viewer@taskhub.io', 'Carol Viewer', '$2b$12$PU9BlXIkzpRrXcLU1rlAjuQeAeLo2A3tnkmYyJh6Uxual2ui54LAi', 'MEMBER', true, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 2. Workspaces
INSERT INTO workspaces (id, name, owner_id, created_at, updated_at)
VALUES 
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b11', 'TaskHub Engineering', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', NOW(), NOW()),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b22', 'Marketing Hub', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 3. Workspace Members
INSERT INTO workspace_members (workspace_id, user_id, role, joined_at)
VALUES 
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'OWNER', NOW()),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'EDITOR', NOW()),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'VIEWER', NOW())
ON CONFLICT (workspace_id, user_id) DO NOTHING;

-- 4. Projects
INSERT INTO projects (id, workspace_id, name, description, status, created_at, updated_at)
VALUES 
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b11', 'TaskHub Backend API', 'Core REST API written in FastAPI', 'ACTIVE', NOW(), NOW()),
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c22', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b11', 'Mobile App Redesign', 'Flutter mobile application project', 'ACTIVE', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 5. Labels
INSERT INTO labels (id, project_id, name, color)
VALUES 
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d11', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'Bug', '#EF4444'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d12', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'Feature', '#3B82F6'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d13', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'DevOps', '#10B981'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d14', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'Urgent', '#F59E0B'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d21', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c22', 'Bug', '#EF4444'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d22', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c22', 'Feature', '#3B82F6'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d23', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c22', 'Design', '#8B5CF6'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380d24', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c22', 'Urgent', '#F59E0B')
ON CONFLICT (id) DO NOTHING;

-- 6. Tasks
INSERT INTO tasks (id, project_id, assignee_id, created_by, title, description, status, priority, due_date, created_at, updated_at)
VALUES 
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e11', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Thiết kế ERD diagram', 'Thực hiện thiết kế ERD diagram cho dự án', 'DONE', 'HIGH', '2026-08-15', NOW(), NOW()),
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e12', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Implement Auth endpoints', 'Viết các API đăng nhập, đăng ký và JWT', 'IN_PROGRESS', 'URGENT', '2026-08-20', NOW(), NOW()),
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e13', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Viết Integration Tests', 'Xây dựng bộ test suite integration cho FastAPI', 'TODO', 'MEDIUM', '2026-08-25', NOW(), NOW()),
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e14', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Setup CI/CD Pipeline', 'Cấu hình GitHub Actions pipeline', 'TODO', 'LOW', '2026-08-30', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 7. Task Labels
INSERT INTO task_labels (task_id, label_id)
VALUES 
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e11', 'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380d12'),
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e12', 'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380d14'),
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e13', 'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380d12'),
    ('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e14', 'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380d13')
ON CONFLICT (task_id, label_id) DO NOTHING;

-- 8. Comments
INSERT INTO comments (id, task_id, author_id, content, created_at)
VALUES 
    ('f0eebc99-9c0b-4ef8-bb6d-6bb9bd380f11', 'e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Vui lòng hoàn thành ERD diagram trước ngày 15.', NOW()),
    ('f0eebc99-9c0b-4ef8-bb6d-6bb9bd380f12', 'e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e11', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'Đã hoàn thành sơ đồ ERD đúng thiết kế.', NOW()),
    ('f0eebc99-9c0b-4ef8-bb6d-6bb9bd380f13', 'e0eebc99-9c0b-4ef8-bb6d-6bb9bd380e12', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'Cần hỗ trợ thêm về JWT refresh token blacklist.', NOW())
ON CONFLICT (id) DO NOTHING;
