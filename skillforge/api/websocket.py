"""WebSocket handler streaming real-time evolution events to the frontend.

Event types emitted (see SPEC.md §WebSocket):
    challenge_designed, generation_started, competitor_started,
    competitor_progress, competitor_finished,
    judging_layer1_complete, judging_layer2_started, judging_layer2_complete,
    judging_layer3_complete, scores_published, breeding_started,
    breeding_report, generation_complete, evolution_complete, cost_update.

Meta mode also emits: meta_domain_generated, meta_domain_evaluated,
meta_generalization_score.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/evolve/{run_id}")
async def evolution_events(websocket: WebSocket, run_id: str) -> None:
    """Stream evolution events for ``run_id``. Real impl lands in Step 8."""
    await websocket.accept()
    try:
        await websocket.send_json(
            {"event": "not_implemented", "run_id": run_id, "detail": "Step 8"}
        )
        await websocket.close()
    except WebSocketDisconnect:
        return
