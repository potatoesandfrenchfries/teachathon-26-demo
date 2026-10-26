"""Create the course and its main book. Idempotent: running it twice changes nothing.

    python -m backend.seed [--preset openstax-physics-1] [--pdf data/books/openstax-physics-1.pdf]

Run `alembic upgrade head` first. The course is physics (decided, DELIBERATION.md Round 9). The
specific book is an assumption until you confirm it: OpenStax University Physics Volume 1.
"""

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from backend.db import default_engine
from backend.models import Book, Course
from backend.models.enums import BookRole, Visibility
from backend.settings import DATA_DIR


@dataclass(frozen=True)
class Preset:
    course_name: str
    book_title: str
    authors: str
    license: str
    license_url: str
    visibility: str
    default_pdf: Path


DEFAULT_PRESET = "openstax-physics-1"

PRESETS: dict[str, Preset] = {
    "openstax-physics-1": Preset(
        course_name="University Physics I",
        book_title="University Physics Volume 1",
        authors="OpenStax",
        license="CC BY 4.0. Confirm the edition and terms before redistribution.",
        license_url="https://openstax.org/details/books/university-physics-volume-1",
        visibility=Visibility.OPEN.value,
        default_pdf=DATA_DIR / "books" / "openstax-physics-1.pdf",
    ),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed(
    session: Session, preset_name: str = DEFAULT_PRESET, pdf: Path | None = None
) -> tuple[Course, Book]:
    preset = PRESETS[preset_name]
    pdf = pdf or preset.default_pdf

    course = session.exec(select(Course).where(Course.name == preset.course_name)).first()
    if course is None:
        course = Course(name=preset.course_name)
        session.add(course)

    book = session.exec(select(Book).where(Book.title == preset.book_title)).first()
    if book is None:
        book = Book(
            title=preset.book_title,
            authors=preset.authors,
            role=BookRole.MAIN.value,
            license=preset.license,
            license_url=preset.license_url,
            visibility=preset.visibility,
        )
        session.add(book)
    # The hash is filled in once the PDF is available, and refreshed if the file changes.
    if pdf.exists():
        book.file_sha256 = file_sha256(pdf)

    session.commit()
    session.refresh(course)
    session.refresh(book)
    return course, book


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preset", default=DEFAULT_PRESET, choices=sorted(PRESETS))
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="load the synthetic sample course (graph and questions) instead of a book preset",
    )
    args = parser.parse_args()

    with Session(default_engine()) as session:
        if args.mock:
            from backend.mockdata.load import seed_mock
            from backend.settings import get_settings

            summary = seed_mock(session, get_settings().edge_min_weight)
            classified = {p: r.classified for p, r in summary.classified.items()}
            print(
                f"mock course {summary.course_id}: {summary.sections} sections, "
                f"{summary.build.nodes_created} nodes and "
                f"{summary.build.edges_created} edges created, "
                f"classified this run {classified}, {summary.questions} questions created"
            )
            return
        try:
            course, book = seed(session, args.preset, args.pdf)
        except OperationalError as error:
            raise SystemExit(
                f"Database not ready ({error.orig}). Run `alembic upgrade head` first."
            ) from error
    sha = book.file_sha256 or "no PDF found yet"
    print(f"course {course.id}: {course.name}\nbook {book.id}: {book.title} ({sha})")


if __name__ == "__main__":
    main()
