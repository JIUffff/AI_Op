"""M5 轨迹记录器：记录执行事件到 SQLite 和 JSON 文件。"""
import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
from .models import Trajectory, TrajectoryEvent


class TrajectoryRecorder:
    """轨迹记录器。

    职责：
    - 创建/追加轨迹记录
    - 持久化到 SQLite 数据库
    - 同时保存为 JSON 文件到 data/trajectories/
    - 提供查询接口（按 skill_id、success 状态过滤）
    """

    def __init__(self, db_path: str = "data/db/local-auto.db", trajectories_dir: str = "data/trajectories") -> None:
        self.db_path = db_path
        self.trajectories_dir = Path(trajectories_dir)
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trajectories (
                    trajectory_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    skill_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    params TEXT,
                    result TEXT,
                    error TEXT,
                    duration_ms REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trajectory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trajectory_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    step_id TEXT,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (trajectory_id) REFERENCES trajectories(trajectory_id)
                )
            """)
            conn.commit()

    def start_recording(self, skill_id: str, skill_version: str, params: dict) -> Trajectory:
        """开始记录一条新轨迹。"""
        trajectory_id = str(uuid.uuid4())
        trajectory = Trajectory(
            trajectory_id=trajectory_id,
            skill_id=skill_id,
            skill_version=skill_version,
            params=params,
        )
        return trajectory

    def record_event(self, trajectory: Trajectory, event: TrajectoryEvent) -> None:
        """记录一个事件。"""
        trajectory.events.append(event)

    def finish_recording(self, trajectory: Trajectory, status: str, result: Optional[dict] = None, error: Optional[dict] = None) -> None:
        """完成轨迹记录并持久化。"""
        trajectory.status = status
        trajectory.finished_at = datetime.utcnow()
        trajectory.result = result
        trajectory.error = error

        if trajectory.started_at and trajectory.finished_at:
            delta = trajectory.finished_at - trajectory.started_at
            trajectory.duration_ms = delta.total_seconds() * 1000

        self._save_to_db(trajectory)
        self._save_to_json(trajectory)

    def _save_to_db(self, trajectory: Trajectory) -> None:
        """保存到 SQLite。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO trajectories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trajectory.trajectory_id,
                    trajectory.skill_id,
                    trajectory.skill_version,
                    trajectory.status,
                    trajectory.started_at.isoformat(),
                    trajectory.finished_at.isoformat() if trajectory.finished_at else None,
                    json.dumps(trajectory.params),
                    json.dumps(trajectory.result) if trajectory.result else None,
                    json.dumps(trajectory.error) if trajectory.error else None,
                    trajectory.duration_ms,
                ),
            )
            for event in trajectory.events:
                conn.execute(
                    "INSERT INTO trajectory_events (trajectory_id, event_type, step_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
                    (
                        trajectory.trajectory_id,
                        event.event_type,
                        event.step_id,
                        event.timestamp.isoformat(),
                        json.dumps(event.details),
                    ),
                )
            conn.commit()

    def _save_to_json(self, trajectory: Trajectory) -> None:
        """保存为 JSON 文件。"""
        filename = f"{trajectory.trajectory_id}.json"
        filepath = self.trajectories_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(trajectory.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    def query_trajectories(
        self,
        skill_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询轨迹记录。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM trajectories WHERE 1=1"
            params: list = []
            if skill_id:
                query += " AND skill_id = ?"
                params.append(skill_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_trajectory(self, trajectory_id: str) -> Optional[dict]:
        """获取单条轨迹详情（含事件）。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM trajectories WHERE trajectory_id = ?", (trajectory_id,)).fetchone()
            if not row:
                return None

            events = conn.execute(
                "SELECT * FROM trajectory_events WHERE trajectory_id = ? ORDER BY id",
                (trajectory_id,),
            ).fetchall()

            result = dict(row)
            result["events"] = [dict(e) for e in events]
            return result

    def get_success_count(self, skill_id: str) -> int:
        """获取某个 Skill 的成功次数。"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM trajectories WHERE skill_id = ? AND status = 'success'",
                (skill_id,),
            ).fetchone()
            return row[0] if row else 0
