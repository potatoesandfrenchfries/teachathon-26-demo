"""Graph routes. Reading is open. Everything that changes the graph needs the admin key."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.api.deps import get_session, require_admin_key
from backend.graph import service
from backend.models.enums import EdgeStatus, EdgeType
from backend.schemas.graph import (
    ApproveRequest,
    CourseOut,
    EdgeCreate,
    EdgeRetype,
    EditOut,
    GraphOut,
)

SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter()
admin = APIRouter(prefix="/admin/graph", dependencies=[Depends(require_admin_key)])


@router.get("/courses")
def courses(session: SessionDep) -> list[CourseOut]:
    return service.list_courses(session)


@router.get("/graph")
def graph(session: SessionDep, course_id: int | None = None) -> GraphOut:
    """The concept graph with evidence for every edge. `course_id` defaults to the first course."""
    return service.get_graph(session, course_id)


@admin.post("/edges")
def add_edge(body: EdgeCreate, session: SessionDep) -> GraphOut:
    return service.add_edge(
        session, body.course_id, body.src_node, body.dst_node, EdgeType(body.type)
    )


@admin.post("/edges/{edge_id}/accept")
def accept_edge(edge_id: int, session: SessionDep) -> GraphOut:
    return service.set_edge_status(session, edge_id, EdgeStatus.ACCEPTED)


@admin.post("/edges/{edge_id}/reject")
def reject_edge(edge_id: int, session: SessionDep) -> GraphOut:
    return service.set_edge_status(session, edge_id, EdgeStatus.REJECTED)


@admin.patch("/edges/{edge_id}")
def retype_edge(edge_id: int, body: EdgeRetype, session: SessionDep) -> GraphOut:
    return service.retype_edge(session, edge_id, EdgeType(body.type))


@admin.delete("/edges/{edge_id}")
def delete_edge(edge_id: int, session: SessionDep) -> GraphOut:
    return service.delete_edge(session, edge_id)


@admin.post("/approve")
def approve(body: ApproveRequest, session: SessionDep) -> GraphOut:
    return service.approve(session, body.course_id, body.accept_remaining)


@admin.get("/edits")
def edits(session: SessionDep, course_id: int | None = None) -> list[EditOut]:
    return [
        EditOut.model_validate(e, from_attributes=True)
        for e in service.list_edits(session, course_id)
    ]
