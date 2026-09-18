"""
Data Models and Enums for SAGE AI Visual Automation Engine v6.
Defines Node, Edge, Workflow, Run, and Execution Context structures.
"""
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import uuid
import time
from datetime import datetime


class NodeCategory(str, Enum):
    EMAIL = "email"
    CALENDAR = "calendar"
    WEB = "web"
    COMPUTER = "computer"
    FILES = "files"
    AI = "ai"
    CODING = "coding"
    GITHUB = "github"
    DATABASE = "database"
    COMMUNICATION = "communication"
    SHOPPING = "shopping"
    REPORTS = "reports"
    LOGIC = "logic"


class NodeType(str, Enum):
    TRIGGER = "trigger"
    ACTION = "action"
    AI = "ai"
    AGENT = "agent"
    CONDITION = "condition"
    LOOP = "loop"
    DELAY = "delay"
    APPROVAL = "approval"
    PARALLEL = "parallel"
    MERGE = "merge"
    FILTER = "filter"
    TRANSFORM = "transform"
    HTTP = "http"
    NOTIFICATION = "notification"
    END = "end"


class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EMAIL_EVENT = "email_event"
    FILE_CHANGE = "file_change"
    GITHUB_EVENT = "github_event"
    WEBHOOK = "webhook"
    API = "api"
    DATA_CHANGE = "data_change"


class StepStatus(str, Enum):
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"
    CANCELLED = "cancelled"


class WorkflowNode:
    """Represents a discrete executable or logical step in a DAG workflow."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        title: str = "New Step",
        node_type: Union[NodeType, str] = NodeType.ACTION,
        category: Union[NodeCategory, str] = NodeCategory.AI,
        action: str = "",
        params: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, float]] = None,
        requires_approval: bool = False,
        retry_count: int = 0,
        retry_delay_sec: float = 2.0,
        condition_expression: str = "",
        description: str = "",
        timeout_sec: float = 60.0
    ):
        self.id = node_id or f"node_{uuid.uuid4().hex[:8]}"
        self.title = title
        self.node_type = NodeType(node_type) if isinstance(node_type, str) else node_type
        self.category = NodeCategory(category) if isinstance(category, str) else category
        self.action = action
        self.params = params or {}
        self.position = position or {"x": 100.0, "y": 100.0}
        self.requires_approval = requires_approval
        self.retry_count = retry_count
        self.retry_delay_sec = retry_delay_sec
        self.condition_expression = condition_expression
        self.description = description
        self.timeout_sec = timeout_sec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.node_type.value,
            "category": self.category.value,
            "action": self.action,
            "params": self.params,
            "position": self.position,
            "requires_approval": self.requires_approval,
            "retry_count": self.retry_count,
            "retry_delay_sec": self.retry_delay_sec,
            "condition_expression": self.condition_expression,
            "description": self.description,
            "timeout_sec": self.timeout_sec
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowNode":
        return cls(
            node_id=data.get("id"),
            title=data.get("title", "Untitled"),
            node_type=data.get("type", NodeType.ACTION.value),
            category=data.get("category", NodeCategory.AI.value),
            action=data.get("action", ""),
            params=data.get("params", {}),
            position=data.get("position", {"x": 100.0, "y": 100.0}),
            requires_approval=data.get("requires_approval", False),
            retry_count=data.get("retry_count", 0),
            retry_delay_sec=data.get("retry_delay_sec", 2.0),
            condition_expression=data.get("condition_expression", ""),
            description=data.get("description", ""),
            timeout_sec=data.get("timeout_sec", 60.0)
        )


class WorkflowEdge:
    """Represents a directed transition between two nodes."""

    def __init__(
        self,
        edge_id: Optional[str] = None,
        source_id: str = "",
        target_id: str = "",
        source_port: str = "output",
        target_port: str = "input",
        label: str = ""
    ):
        self.id = edge_id or f"edge_{uuid.uuid4().hex[:8]}"
        self.source_id = source_id
        self.target_id = target_id
        self.source_port = source_port
        self.target_port = target_port
        self.label = label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "source_port": self.source_port,
            "target_port": self.target_port,
            "label": self.label
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowEdge":
        return cls(
            edge_id=data.get("id"),
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            source_port=data.get("source_port", "output"),
            target_port=data.get("target_port", "input"),
            label=data.get("label", "")
        )


class Workflow:
    """Complete workflow definition containing DAG nodes, edges, and metadata."""

    def __init__(
        self,
        workflow_id: Optional[str] = None,
        name: str = "New Workflow",
        description: str = "",
        category: str = "general",
        trigger_type: str = "manual",
        is_active: bool = True,
        nodes: Optional[List[WorkflowNode]] = None,
        edges: Optional[List[WorkflowEdge]] = None,
        variables: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None
    ):
        self.id = workflow_id or f"wf_{uuid.uuid4().hex[:10]}"
        self.name = name
        self.description = description
        self.category = category
        self.trigger_type = trigger_type
        self.is_active = is_active
        self.nodes = nodes or []
        self.edges = edges or []
        self.variables = variables or {}
        now = datetime.now().isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_outgoing_edges(self, node_id: str, port: Optional[str] = None) -> List[WorkflowEdge]:
        edges = [e for e in self.edges if e.source_id == node_id]
        if port is not None:
            edges = [e for e in edges if e.source_port == port]
        return edges

    def get_incoming_edges(self, node_id: str) -> List[WorkflowEdge]:
        return [e for e in self.edges if e.target_id == node_id]

    def get_root_nodes(self) -> List[WorkflowNode]:
        target_ids = {e.target_id for e in self.edges}
        roots = [n for n in self.nodes if n.id not in target_ids]
        if not roots and self.nodes:
            return [self.nodes[0]]
        return roots

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "trigger_type": self.trigger_type,
            "is_active": self.is_active,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "variables": self.variables,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        edges = [WorkflowEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(
            workflow_id=data.get("id"),
            name=data.get("name", "Untitled Workflow"),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            trigger_type=data.get("trigger_type", "manual"),
            is_active=bool(data.get("is_active", True)),
            nodes=nodes,
            edges=edges,
            variables=data.get("variables", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )


class StepResult:
    """Stores execution metrics and output for a single node run."""

    def __init__(
        self,
        node_id: str,
        status: StepStatus = StepStatus.PENDING,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Any] = None,
        error_message: Optional[str] = None,
        duration_ms: float = 0.0,
        logs: Optional[List[str]] = None
    ):
        self.node_id = node_id
        self.status = status
        self.input_data = input_data or {}
        self.output_data = output_data
        self.error_message = error_message
        self.duration_ms = duration_ms
        self.logs = logs or []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status.value if isinstance(self.status, StepStatus) else str(self.status),
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "logs": self.logs,
            "timestamp": self.timestamp
        }
