from sqlmodel import Field, SQLModel


class Section(SQLModel, table=True):
    __tablename__ = "section"

    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    number: str
    title: str
    page_start: int | None = None
    page_end: int | None = None
    parent_id: int | None = Field(default=None, foreign_key="section.id")


class NumberedResult(SQLModel, table=True):
    __tablename__ = "numbered_result"

    id: int | None = Field(default=None, primary_key=True)
    section_id: int = Field(foreign_key="section.id", index=True)
    label: str  # for example "3.22"
    kind: str  # definition, theorem, proposition, ...
    page: int | None = None


class CrossRef(SQLModel, table=True):
    """How often one numbered result refers to another (rolled up into section edge weights)."""

    __tablename__ = "cross_ref"

    src_result_id: int = Field(foreign_key="numbered_result.id", primary_key=True)
    dst_result_id: int = Field(foreign_key="numbered_result.id", primary_key=True)
    count: int = 1
