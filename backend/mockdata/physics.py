"""Synthetic physics sample data: a small curriculum, its cross-references and its true structure.

This stands in for what ingestion will extract from a real book. It is invented, not copied from
any textbook. `PAIRS` doubles as the ground truth that the mock classifier answers from.
"""

BOOK_TITLE = "Mock Physics (sample data)"
COURSE_NAME = "Mock Physics (sample data)"

# (number, title)
SECTIONS: list[tuple[str, str]] = [
    ("1.1", "Units and dimensional analysis"),
    ("1.2", "Vectors and components"),
    ("2.1", "Position, displacement and velocity"),
    ("2.2", "Acceleration and constant-acceleration motion"),
    ("2.3", "Free fall"),
    ("2.4", "Projectile motion"),
    ("3.1", "Newton's first and second laws"),
    ("3.2", "Newton's third law and free-body diagrams"),
    ("3.3", "Friction"),
    ("3.4", "Circular motion and centripetal force"),
    ("4.1", "Work and the work-energy theorem"),
    ("4.2", "Kinetic and potential energy"),
    ("4.3", "Conservation of energy"),
    ("4.4", "Power"),
    ("5.1", "Momentum and impulse"),
    ("5.2", "Conservation of momentum and collisions"),
]

WORLDS: dict[str, str] = {
    "1": "Foundations",
    "2": "Kinematics",
    "3": "Dynamics",
    "4": "Energy",
    "5": "Momentum",
}

# Three numbered results per section, in the style of a physics text.
RESULT_KINDS: list[tuple[str, str]] = [
    ("equation", "Eq. {n}.1"),
    ("example", "Example {n}.1"),
    ("definition", "Def. {n}.1"),
]

# (earlier section, later section, cross-references between them, true relationship)
PAIRS: list[tuple[str, str, int, str]] = [
    ("1.1", "1.2", 2, "optional"),
    ("1.1", "2.1", 3, "required"),
    ("1.2", "2.1", 4, "required"),
    ("2.1", "2.2", 6, "required"),
    ("2.2", "2.3", 5, "required"),
    ("2.3", "2.4", 3, "required"),
    ("1.2", "2.4", 4, "required"),
    ("2.2", "2.4", 2, "optional"),  # implied by 2.2 -> 2.3 -> 2.4, so reduction hides it
    ("2.2", "3.1", 4, "required"),
    ("1.2", "3.1", 3, "required"),
    ("3.1", "3.2", 5, "required"),
    ("3.1", "3.3", 2, "required"),  # implied by 3.1 -> 3.2 -> 3.3
    ("3.2", "3.3", 4, "required"),
    ("3.1", "3.4", 3, "required"),
    ("2.1", "3.4", 2, "optional"),
    ("3.1", "4.1", 3, "required"),
    ("1.2", "4.1", 3, "required"),
    ("4.1", "4.2", 5, "required"),
    ("2.1", "4.2", 2, "optional"),
    ("4.2", "4.3", 6, "required"),
    ("2.3", "4.3", 2, "optional"),
    ("4.1", "4.4", 4, "required"),
    ("2.1", "4.4", 2, "required"),
    ("3.4", "4.4", 2, "none"),  # incidental: a pair of references that is not a dependency
    ("3.1", "5.1", 4, "required"),
    ("2.1", "5.1", 2, "optional"),
    ("5.1", "5.2", 6, "required"),
    ("4.3", "5.2", 3, "optional"),
    ("3.2", "5.2", 2, "optional"),
    # Below the default threshold of 2, so they never become candidate edges.
    ("1.1", "2.3", 1, "none"),
    ("2.2", "3.3", 1, "none"),
]

# References that point forwards (an earlier section mentions a later one). They still count
# toward the pair's weight.
FORWARD_REFS: list[tuple[str, str, int]] = [("2.2", "3.1", 1)]


def truth(src_number: str, dst_number: str) -> str:
    """The true relationship for a pair of section numbers, `none` if the pair is not listed."""
    for earlier, later, _count, relation in PAIRS:
        if (earlier, later) == (src_number, dst_number):
            return relation
    return "none"
