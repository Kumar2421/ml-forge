"""projects/registry.py — Project persistence in SQLite."""

from __future__ import annotations

from datetime import datetime, timezone

from database.connection import get_db
from models.project import Project


async def upsert_project(project: Project) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO projects (id, name, path, created_at, last_opened, status)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name,
             path=excluded.path,
             last_opened=excluded.last_opened,
             status=excluded.status
        """,
        (
            project.id,
            project.name,
            project.path,
            project.created_at,
            project.last_opened,
            project.status,
        ),
    )
    await db.commit()


async def list_projects(limit: int = 200, offset: int = 0) -> list[Project]:
    db = await get_db()
    async with db.execute(
        """SELECT id, name, path, created_at, last_opened, status
           FROM projects
           ORDER BY datetime(last_opened) DESC
           LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ) as cur:
        rows = await cur.fetchall()
    return [Project(**dict(r)) for r in rows]


async def delete_project(project_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    await db.commit()
    return (cur.rowcount or 0) > 0


async def get_project(project_id: str) -> Project | None:
    db = await get_db()
    async with db.execute(
        "SELECT id, name, path, created_at, last_opened, status FROM projects WHERE id = ?",
        (project_id,),
    ) as cur:
        row = await cur.fetchone()
    return Project(**dict(row)) if row else None


async def touch_last_opened(project_id: str) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE projects SET last_opened = ? WHERE id = ?",
        (now, project_id),
    )
    await db.commit()

