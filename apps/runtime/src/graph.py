from langgraph.graph import StateGraph, END
from .state import TaskState
import logging

logger = logging.getLogger("runtime.graph")


def parse_intent(state: TaskState) -> TaskState:
    state["steps"].append("intent_parsed")
    state["current_step"] = 1
    return state


def execute_step(state: TaskState) -> TaskState:
    state["steps"].append("step_executed")
    state["current_step"] = 2
    return state


def verify_result(state: TaskState) -> TaskState:
    state["steps"].append("result_verified")
    state["status"] = "success"
    return state


def create_workflow() -> StateGraph:
    workflow = StateGraph(TaskState)

    workflow.add_node("parse", parse_intent)
    workflow.add_node("execute", execute_step)
    workflow.add_node("verify", verify_result)

    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "execute")
    workflow.add_edge("execute", "verify")
    workflow.add_edge("verify", END)

    return workflow.compile()
