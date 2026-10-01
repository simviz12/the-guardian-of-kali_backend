from pydantic import BaseModel
class LogManualCommandPayload(BaseModel):
    command: str
    session_id: str | None = None

@app.post("/history/log", tags=["Audit & History"])
async def log_manual_command(
    payload: LogManualCommandPayload,
    repo: SessionRepository = Depends(get_session_repository)
):
    import uuid
    from datetime import datetime
    from src.core.entities.command import Command, CommandOrigin, PolicyDecision, RiskLevel
    
    cmd = Command(
        id=uuid.uuid4(),
        text=payload.command,
        timestamp=datetime.utcnow(),
        origin=CommandOrigin.USER,
        user="carlos",  # default
        risk_level=RiskLevel.LOW,
        policy_decision=PolicyDecision.EXECUTED,
        session_id=uuid.UUID(payload.session_id) if payload.session_id else None
    )
    await repo.save_command(cmd)
    return {"ok": True}
