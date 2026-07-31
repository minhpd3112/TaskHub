import enum


class UserRole(str, enum.Enum):
    """System-wide user roles."""

    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class WorkspaceRole(str, enum.Enum):
    """Workspace-level user roles."""

    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class ProjectStatus(str, enum.Enum):
    """Project status."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class TaskStatus(str, enum.Enum):
    """Task status."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"


class TaskPriority(str, enum.Enum):
    """Task priority."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"
