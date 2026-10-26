"""Import every table here so that SQLModel.metadata (and Alembic) sees them."""

from backend.models.course import Book, Course
from backend.models.graph import ConceptNode, Edge, GraphEdit
from backend.models.ingest import CrossRef, NumberedResult, Section
from backend.models.llm import LLMCall
from backend.models.questions import Question, QuestionTag

__all__ = [
    "Book",
    "ConceptNode",
    "Course",
    "CrossRef",
    "Edge",
    "GraphEdit",
    "LLMCall",
    "NumberedResult",
    "Question",
    "QuestionTag",
    "Section",
]
