from langgraph.graph import StateGraph, END
from .state import TaskState
import logging

logger = logging.getLogger("runtime.graph")


def parse_intent(state: TaskState) -> TaskState:
    state.steps.append("intent_parsed")
    state.current_step = 1
    return state


def execute_step(state: TaskState) -> TaskState:
    state.steps.append("step_executed")
    state.current_step = 2
    return state


def verify_result(state: TaskState) -> TaskState:
    state.steps.append("result_verified")
    state.status = "success"
    return state


def handle_failure(state: TaskState) -> TaskState:
    state.steps.append("failure_handled")
    state.status = "failed"
    state.recovery_attempted = True
    logger.error(f"Task {state.task_id} failed at step {state.current_step}")
    return state


def should_recover(state: TaskState) -> str:
    if state.status == "failed" and state.recovery_attempted:
        return "end"
    elif state.status == "failed":
        return "recover"
    return "continue"


def attempt_recovery(state: TaskState) -> TaskState:
    state.steps.append("recovery_attempted")
    state.status = "recovered"
    logger.info(f"Task {state.task_id} recovered")
    return state


def create_workflow() -> StateGraph:
    workflow = StateGraph(TaskState)

    workflow.add_node("parse", parse_intent)
    workflow.add_node("execute", execute_step)
    workflow.add_node("verify", verify_result)
    workflow.add_node("recover", attempt_recovery)
    workflow.add_node("failure", handle_failure)

    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "execute")
    workflow.add_edge("execute", "verify")
    workflow.add_conditional_edges(
        "verify",
        lambda s: "end" if s.status == "success" else "failure",
        {"end": END, "failure": "failure"},
    )
    workflow.add_conditional_edges(
        "failure",
        should_recover,
        {"recover": "recover", "end": END},
    )
    workflow.add_edge("recover", END)

    return workflow.compile()
