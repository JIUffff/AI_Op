import pytest
from src.state import TaskState
from src.graph import create_workflow


@pytest.fixture
def workflow():
    return create_workflow()


def test_empty_task_succeeds(workflow):
    state: TaskState = {
        "task_id": "test_001",
        "user_input": "",
        "skill_id": None,
        "status": "pending",
        "steps": [],
        "current_step": 0,
        "error_code": None,
        "started_at": None,
        "finished_at": None,
        "recovery_attempted": False,
    }

    result = workflow.invoke(state)

    assert result["status"] == "success"
    assert "intent_parsed" in result["steps"]
    assert "step_executed" in result["steps"]
    assert "result_verified" in result["steps"]
    assert result["current_step"] == 2
