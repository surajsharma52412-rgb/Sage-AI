from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.get("/agents")
def list_agents():
    return [{"id": "sage-coder", "name": "Sage Coding Agent", "status": "active"}]
