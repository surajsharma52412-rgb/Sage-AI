"""
Specialized Internal Coding Sub-Agents for SAGE Coding Agent.
Provides the 10 internal specialized workers specified in Section 9:
1. Architect
2. Backend Coder
3. Frontend Coder
4. Database Engineer
5. Debugger
6. Tester
7. Security Reviewer
8. Code Reviewer
9. DevOps Engineer
10. Documentation Engineer
"""
from .base_sub_agent import BaseSubAgent
from .architect_agent import ArchitectAgent
from .backend_agent import BackendAgent
from .frontend_agent import FrontendAgent
from .database_worker import DatabaseWorker
from .debugger_worker import DebuggerWorker
from .qa_agent import QAAgent
from .security_worker import SecurityWorker
from .reviewer_worker import ReviewerWorker
from .devops_agent import DevOpsAgent
from .documentation_agent import DocumentationAgent

__all__ = [
    "BaseSubAgent",
    "ArchitectAgent",
    "BackendAgent",
    "FrontendAgent",
    "DatabaseWorker",
    "DebuggerWorker",
    "QAAgent",
    "SecurityWorker",
    "ReviewerWorker",
    "DevOpsAgent",
    "DocumentationAgent"
]
