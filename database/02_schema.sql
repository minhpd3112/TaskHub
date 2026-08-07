-- TaskHub Database Schema Script (Pure PostgreSQL DDL)

-- 1. Create ENUM Types
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN 
        CREATE TYPE user_role AS ENUM ('ADMIN', 'MEMBER'); 
    END IF; 
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workspace_role') THEN 
        CREATE TYPE workspace_role AS ENUM ('OWNER', 'EDITOR', 'VIEWER'); 
    END IF; 
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN 
        CREATE TYPE project_status AS ENUM ('ACTIVE', 'ARCHIVED'); 
    END IF; 
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_status') THEN 
        CREATE TYPE task_status AS ENUM ('TODO', 'IN_PROGRESS', 'IN_REVIEW', 'DONE'); 
    END IF; 
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_priority') THEN 
        CREATE TYPE task_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT'); 
    END IF; 
END $$;

-- 2. Create Tables in dependency order

-- 2.1 users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'MEMBER',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- 2.2 workspaces
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_workspaces_owner_id ON workspaces (owner_id);

-- 2.3 workspace_members
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role workspace_role NOT NULL DEFAULT 'VIEWER',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_workspace_members_workspace_id ON workspace_members (workspace_id);
CREATE INDEX IF NOT EXISTS ix_workspace_members_user_id ON workspace_members (user_id);

-- 2.4 projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status project_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_projects_workspace_id ON projects (workspace_id);
CREATE INDEX IF NOT EXISTS ix_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS ix_projects_workspace_status ON projects (workspace_id, status);

-- 2.5 tasks
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    assignee_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status task_status NOT NULL DEFAULT 'TODO',
    priority task_priority NOT NULL DEFAULT 'MEDIUM',
    due_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_tasks_project_id ON tasks (project_id);
CREATE INDEX IF NOT EXISTS ix_tasks_assignee_id ON tasks (assignee_id);
CREATE INDEX IF NOT EXISTS ix_tasks_created_by ON tasks (created_by);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS ix_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS ix_tasks_project_status ON tasks (project_id, status);
CREATE INDEX IF NOT EXISTS ix_tasks_project_priority ON tasks (project_id, priority);
CREATE INDEX IF NOT EXISTS ix_tasks_project_assignee ON tasks (project_id, assignee_id);
CREATE INDEX IF NOT EXISTS ix_tasks_project_created_at_desc ON tasks (project_id, created_at DESC);

-- 2.6 labels
CREATE TABLE IF NOT EXISTS labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    color VARCHAR(7) NOT NULL CONSTRAINT ck_labels_color_hex CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT uq_labels_project_id_name UNIQUE (project_id, name)
);
CREATE INDEX IF NOT EXISTS ix_labels_project_id ON labels (project_id);

-- 2.7 task_labels
CREATE TABLE IF NOT EXISTS task_labels (
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    label_id UUID NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, label_id)
);

-- 2.8 comments
CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_comments_task_id ON comments (task_id);
CREATE INDEX IF NOT EXISTS ix_comments_task_created_at ON comments (task_id, created_at);

-- 2.9 user_notification_settings
CREATE TABLE IF NOT EXISTS user_notification_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    task_assigned BOOLEAN NOT NULL DEFAULT true,
    task_status_changed BOOLEAN NOT NULL DEFAULT true,
    task_commented BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_user_notification_settings_user_id ON user_notification_settings (user_id);
