"""M5 轨迹模块测试：TrajectoryRecorder, SkillDistiller, ReplayEvaluator, PromotionEngine。"""
import json
import sqlite3
import tempfile
import shutil
import pytest
from pathlib import Path
from datetime import datetime

from src.trajectory.models import Trajectory, TrajectoryEvent, CandidateSkill
from src.trajectory.recorder import TrajectoryRecorder
from src.trajectory.distiller import SkillDistiller
from src.trajectory.replay import ReplayEvaluator
from src.trajectory.promotion import PromotionEngine


class TestTrajectoryModels:
    def test_trajectory_event_creation(self):
        event = TrajectoryEvent(
            event_type="step_start",
            skill_id="test_skill",
            step_id="step_1",
            details={"action": "open"},
        )
        assert event.event_type == "step_start"
        assert event.skill_id == "test_skill"
        assert event.step_id == "step_1"

    def test_trajectory_creation(self):
        traj = Trajectory(
            trajectory_id="test-uuid",
            skill_id="test_skill",
            skill_version="1.0.0",
            status="success",
            params={"file": "test.py"},
        )
        assert traj.trajectory_id == "test-uuid"
        assert traj.skill_id == "test_skill"
        assert traj.status == "success"

    def test_candidate_skill_creation(self):
        candidate = CandidateSkill(
            skill_id="test_skill",
            version="1.0.0-candidate",
            source_trajectories=["uuid1", "uuid2", "uuid3"],
        )
        assert candidate.status == "candidate"
        assert len(candidate.source_trajectories) == 3


class TestTrajectoryRecorder:
    @pytest.fixture
    def recorder(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        traj_dir = str(tmp_path / "trajectories")
        return TrajectoryRecorder(db_path=db_path, trajectories_dir=traj_dir)

    def test_start_recording(self, recorder):
        traj = recorder.start_recording("test_skill", "1.0.0", {"file": "test.py"})
        assert traj.skill_id == "test_skill"
        assert traj.skill_version == "1.0.0"
        assert traj.params["file"] == "test.py"

    def test_record_event(self, recorder):
        traj = recorder.start_recording("test_skill", "1.0.0", {})
        event = TrajectoryEvent(event_type="step_start", skill_id="test_skill", step_id="s1")
        recorder.record_event(traj, event)
        assert len(traj.events) == 1
        assert traj.events[0].event_type == "step_start"

    def test_finish_recording_saves_to_db_and_json(self, recorder):
        traj = recorder.start_recording("test_skill", "1.0.0", {"file": "test.py"})
        event = TrajectoryEvent(event_type="step_end", skill_id="test_skill", step_id="s1")
        recorder.record_event(traj, event)
        recorder.finish_recording(traj, status="success", result={"message": "ok"})

        # 检查 JSON 文件
        json_files = list(Path(recorder.trajectories_dir).glob("*.json"))
        assert len(json_files) == 1

        # 检查数据库
        with sqlite3.connect(recorder.db_path) as conn:
            row = conn.execute("SELECT * FROM trajectories WHERE trajectory_id = ?", (traj.trajectory_id,)).fetchone()
            assert row is not None
            assert row[3] == "success"  # status column

    def test_query_trajectories(self, recorder):
        traj = recorder.start_recording("test_skill", "1.0.0", {})
        recorder.finish_recording(traj, status="success")

        results = recorder.query_trajectories(skill_id="test_skill")
        assert len(results) == 1
        assert results[0]["skill_id"] == "test_skill"

    def test_query_by_status(self, recorder):
        traj1 = recorder.start_recording("test_skill", "1.0.0", {})
        recorder.finish_recording(traj1, status="success")

        traj2 = recorder.start_recording("test_skill", "1.0.0", {})
        recorder.finish_recording(traj2, status="failed")

        success_results = recorder.query_trajectories(skill_id="test_skill", status="success")
        assert len(success_results) == 1

    def test_get_trajectory_with_events(self, recorder):
        traj = recorder.start_recording("test_skill", "1.0.0", {})
        event = TrajectoryEvent(event_type="step_end", skill_id="test_skill", step_id="s1")
        recorder.record_event(traj, event)
        recorder.finish_recording(traj, status="success")

        result = recorder.get_trajectory(traj.trajectory_id)
        assert result is not None
        assert len(result["events"]) == 1

    def test_get_trajectory_not_found(self, recorder):
        result = recorder.get_trajectory("nonexistent")
        assert result is None

    def test_get_success_count(self, recorder):
        traj1 = recorder.start_recording("test_skill", "1.0.0", {})
        recorder.finish_recording(traj1, status="success")

        traj2 = recorder.start_recording("test_skill", "1.0.0", {})
        recorder.finish_recording(traj2, status="failed")

        assert recorder.get_success_count("test_skill") == 1


class TestSkillDistiller:
    @pytest.fixture
    def distiller(self, tmp_path):
        skills_dir = str(tmp_path / "skills")
        return SkillDistiller(skills_dir=skills_dir)

    def test_distill_requires_minimum_trajectories(self, distiller):
        with pytest.raises(ValueError, match="至少需要 3 条成功轨迹"):
            distiller.distill("test_skill", [{"trajectory_id": "1"}, {"trajectory_id": "2"}])

    def test_distill_creates_candidate_skill(self, distiller, tmp_path):
        trajectories = [
            {
                "trajectory_id": "uuid1",
                "params": {"file": "test.py"},
                "events": [
                    {"event_type": "step_start", "step_id": "s1"},
                    {"event_type": "step_end", "step_id": "s1", "details": {"action": "open", "engine": "vscode"}},
                ],
            },
            {
                "trajectory_id": "uuid2",
                "params": {"file": "test.py"},
                "events": [
                    {"event_type": "step_start", "step_id": "s1"},
                    {"event_type": "step_end", "step_id": "s1", "details": {"action": "open", "engine": "vscode"}},
                ],
            },
            {
                "trajectory_id": "uuid3",
                "params": {"file": "test.py"},
                "events": [
                    {"event_type": "step_start", "step_id": "s1"},
                    {"event_type": "step_end", "step_id": "s1", "details": {"action": "open", "engine": "vscode"}},
                ],
            },
        ]

        output_dir = tmp_path / "output"
        candidate = distiller.distill("test_skill", trajectories, output_dir)

        assert candidate.skill_id == "test_skill"
        assert "candidate" in candidate.version
        assert len(candidate.source_trajectories) == 3

        # 检查文件
        assert (output_dir / "workflow.yaml").exists()
        assert (output_dir / "recovery.yaml").exists()
        assert (output_dir / "metadata.json").exists()

    def test_distill_generates_correct_version(self, distiller, tmp_path):
        trajectories = [
            {
                "trajectory_id": "uuid1",
                "params": {},
                "events": [
                    {"event_type": "step_end", "step_id": "s1", "details": {"action": "open", "engine": "vscode"}},
                ],
            },
            {
                "trajectory_id": "uuid2",
                "params": {},
                "events": [
                    {"event_type": "step_end", "step_id": "s1", "details": {"action": "open", "engine": "vscode"}},
                ],
            },
            {
                "trajectory_id": "uuid3",
                "params": {},
                "events": [
                    {"event_type": "step_end", "step_id": "s1", "details": {"action": "open", "engine": "vscode"}},
                ],
            },
        ]

        output_dir = tmp_path / "output"
        candidate = distiller.distill("test_skill", trajectories, output_dir)
        assert "candidate" in candidate.version


class TestReplayEvaluator:
    def test_evaluate_simulated_success(self):
        evaluator = ReplayEvaluator()
        candidate = {"skill_id": "test_skill", "version": "1.0.0"}
        result = evaluator.evaluate(candidate, iterations=10)
        assert result["success_count"] == 10
        assert result["failure_count"] == 0
        assert result["success_rate"] == 1.0
        assert result["can_promote"] is True

    def test_evaluate_with_executor_success(self):
        class MockExecutor:
            def execute(self, skill, params):
                return {"success": True}

        evaluator = ReplayEvaluator(executor=MockExecutor())
        result = evaluator.evaluate({"skill_id": "test"}, iterations=5)
        assert result["success_rate"] == 1.0
        assert result["replay_count"] == 5

    def test_evaluate_with_executor_failure(self):
        call_count = 0

        class FailingExecutor:
            def execute(self, skill, params):
                nonlocal call_count
                call_count += 1
                if call_count <= 3:
                    return {"success": True}
                return {"success": False, "error": "failed"}

        evaluator = ReplayEvaluator(executor=FailingExecutor())
        result = evaluator.evaluate({"skill_id": "test"}, iterations=10)
        assert result["success_count"] == 3
        assert result["failure_count"] == 7
        assert result["success_rate"] == 0.3
        assert result["can_promote"] is False
        assert len(result["failures"]) == 7

    def test_evaluate_edge_case_zero_iterations(self):
        evaluator = ReplayEvaluator()
        result = evaluator.evaluate({"skill_id": "test"}, iterations=0)
        assert result["success_rate"] == 0.0
        assert result["can_promote"] is False


class TestPromotionEngine:
    @pytest.fixture
    def engine(self, tmp_path):
        skills_dir = str(tmp_path / "skills")
        backups_dir = str(tmp_path / "backups")
        return PromotionEngine(skills_dir=skills_dir, backups_dir=backups_dir)

    def test_try_promote_success_rate_below_threshold(self, engine):
        result = engine.try_promote(Path("/nonexistent"), {"success_rate": 0.7})
        assert result["promoted"] is False
        assert "80%" in result["reason"]

    def test_try_promote_success(self, engine, tmp_path):
        candidate_dir = tmp_path / "candidate"
        candidate_dir.mkdir()

        metadata = {
            "skill_id": "test_skill",
            "version": "2.0.0-candidate",
            "status": "candidate",
        }
        with open(candidate_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        replay_result = {"success_rate": 0.9, "replay_count": 10}
        result = engine.try_promote(candidate_dir, replay_result)

        assert result["promoted"] is True
        assert "80%" in result["reason"] or "90%" in result["reason"]
        assert result["new_path"] is not None

        # 检查新版本的 metadata 已更新
        new_metadata_path = Path(result["new_path"]) / "metadata.json"
        with open(new_metadata_path) as f:
            new_metadata = json.load(f)
        assert new_metadata["status"] == "active"
        assert "candidate" not in new_metadata["version"]
        assert "promoted_at" in new_metadata

    def test_try_promote_backs_up_old_version(self, engine, tmp_path):
        # 创建已存在的 Skill 目录
        existing_dir = engine.skills_dir / "test_skill"
        existing_dir.mkdir()
        (existing_dir / "old_file.txt").write_text("old content")

        candidate_dir = tmp_path / "candidate"
        candidate_dir.mkdir()
        metadata = {"skill_id": "test_skill", "version": "2.0.0-candidate"}
        with open(candidate_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        replay_result = {"success_rate": 0.9, "replay_count": 10}
        result = engine.try_promote(candidate_dir, replay_result)

        assert result["promoted"] is True
        assert result["backup_path"] is not None

        # 检查备份目录存在
        backup_dir = Path(result["backup_path"])
        assert backup_dir.exists()
        assert (backup_dir / "old_file.txt").read_text() == "old content"

    def test_try_promote_missing_metadata(self, engine, tmp_path):
        candidate_dir = tmp_path / "candidate"
        candidate_dir.mkdir()

        replay_result = {"success_rate": 0.9, "replay_count": 10}
        result = engine.try_promote(candidate_dir, replay_result)

        assert result["promoted"] is False
        assert "metadata.json" in result["reason"]
