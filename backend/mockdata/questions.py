"""Synthetic physics questions for the sample course.

Numeric answers are computed here, not typed in, so the key cannot drift from the statement.
Each question lists the section numbers it exercises. The first is the primary tag.
"""

import math
from dataclasses import dataclass, field

G = 9.8


@dataclass(frozen=True)
class MockQuestion:
    sections: tuple[str, ...]  # tags; the first is the primary one
    latex: str
    type: str  # "numeric" or "mcq"
    answer_key: dict
    difficulty: float  # prior on a logit-like scale; negative is easier
    options: list[dict] | None = None
    ref: str = field(default="")


def _numeric(sections, latex, value, unit, difficulty, tol=0.02) -> MockQuestion:
    key = {"value": round(value, 3), "unit": unit, "tolerance_rel": tol}
    return MockQuestion(tuple(sections), latex, "numeric", key, difficulty)


def _mcq(sections, latex, options, difficulty) -> MockQuestion:
    """`options` is a list of (text, misconception). The one with no misconception is correct."""
    labelled = [
        {"label": "ABCD"[i], "text": text, "misconception": misconception}
        for i, (text, misconception) in enumerate(options)
    ]
    correct = next(o["label"] for o in labelled if o["misconception"] is None)
    return MockQuestion(tuple(sections), latex, "mcq", {"correct": correct}, difficulty, labelled)


def build() -> list[MockQuestion]:
    q: list[MockQuestion] = []

    # 1.1 Units
    q.append(
        _numeric(
            ["1.1"],
            r"Convert a speed of $72\ \text{km/h}$ to $\text{m/s}$.",
            72 / 3.6,
            "m/s",
            -1.0,
        )
    )
    q.append(
        _mcq(
            ["1.1"],
            r"Which combination of base units has the dimensions of force?",
            [
                (r"$\text{kg}\cdot\text{m}/\text{s}^2$", None),
                (r"$\text{kg}\cdot\text{m}/\text{s}$", "Confuses force with momentum"),
                (r"$\text{kg}\cdot\text{m}^2/\text{s}^2$", "Confuses force with energy"),
                (r"$\text{kg}/(\text{m}\cdot\text{s}^2)$", "Assembles the base units wrongly"),
            ],
            -0.5,
        )
    )

    # 1.2 Vectors
    q.append(
        _numeric(
            ["1.2"],
            r"A displacement has components $3.0\ \text{m}$ and $4.0\ \text{m}$. "
            r"What is its magnitude?",
            math.hypot(3.0, 4.0),
            "m",
            -1.0,
        )
    )
    q.append(
        _numeric(
            ["1.2"],
            r"A $10\ \text{N}$ force points $30^\circ$ above the $x$-axis. "
            r"What is its $x$-component?",
            10 * math.cos(math.radians(30)),
            "N",
            -0.3,
        )
    )

    # 2.1 Velocity
    q.append(
        _numeric(
            ["2.1"],
            r"A runner covers $100\ \text{m}$ east in $12.5\ \text{s}$. "
            r"What is the average velocity?",
            100 / 12.5,
            "m/s",
            -1.0,
        )
    )
    q.append(
        _numeric(
            ["2.1"],
            r"A particle's position is $x(t)=2t^2-3t$ (metres, with $t$ in seconds). "
            r"What is its velocity at $t=2\ \text{s}$?",
            4 * 2 - 3,
            "m/s",
            0.3,
        )
    )

    # 2.2 Constant acceleration
    q.append(
        _numeric(
            ["2.2"],
            r"A car speeds up from $10\ \text{m/s}$ to $30\ \text{m/s}$ in $5.0\ \text{s}$. "
            r"What is its acceleration?",
            (30 - 10) / 5.0,
            "m/s^2",
            -0.8,
        )
    )
    q.append(
        _numeric(
            ["2.2"],
            r"Starting from rest with $a=2.0\ \text{m/s}^2$, how far does a cart travel in "
            r"$6.0\ \text{s}$?",
            0.5 * 2.0 * 6.0**2,
            "m",
            -0.5,
        )
    )
    q.append(
        _numeric(
            ["2.2"],
            r"A car brakes at $5.0\ \text{m/s}^2$ from $20\ \text{m/s}$. "
            r"What is its stopping distance?",
            20.0**2 / (2 * 5.0),
            "m",
            0.2,
        )
    )

    # 2.3 Free fall
    q.append(
        _numeric(
            ["2.3", "2.2"],
            rf"A ball is dropped from a height of $45\ \text{{m}}$. How long does it take to "
            rf"reach the ground? Take $g={G}\ \text{{m/s}}^2$.",
            math.sqrt(2 * 45 / G),
            "s",
            0.0,
        )
    )
    q.append(
        _numeric(
            ["2.3"],
            rf"A stone is thrown straight up at $14.7\ \text{{m/s}}$. What maximum height does it "
            rf"reach? Take $g={G}\ \text{{m/s}}^2$.",
            14.7**2 / (2 * G),
            "m",
            0.3,
        )
    )

    # 2.4 Projectiles
    q.append(
        _numeric(
            ["2.4", "1.2", "2.3"],
            rf"A projectile is launched at $20\ \text{{m/s}}$, $30^\circ$ above the horizontal. "
            rf"What is its time of flight on level ground? Take $g={G}\ \text{{m/s}}^2$.",
            2 * 20 * math.sin(math.radians(30)) / G,
            "s",
            0.6,
        )
    )
    q.append(
        _numeric(
            ["2.4", "1.2"],
            rf"The same projectile ($20\ \text{{m/s}}$ at $30^\circ$) lands on level ground. "
            rf"What is its horizontal range? Take $g={G}\ \text{{m/s}}^2$.",
            20**2 * math.sin(math.radians(60)) / G,
            "m",
            0.8,
        )
    )

    # 3.1 Newton I and II
    q.append(
        _numeric(
            ["3.1"],
            r"A net force of $12\ \text{N}$ acts on a $3.0\ \text{kg}$ object. "
            r"What is its acceleration?",
            12 / 3.0,
            "m/s^2",
            -1.0,
        )
    )
    q.append(
        _mcq(
            ["3.1"],
            r"An object moves at constant velocity in a straight line. "
            r"What is the net force on it?",
            [
                ("Zero", None),
                (
                    "A force in the direction of motion",
                    "Believes a force is needed to keep an object moving",
                ),
                ("A force opposite to the motion", "Confuses net force with friction"),
                ("It cannot be determined", "Does not apply Newton's first law"),
            ],
            -0.3,
        )
    )

    # 3.2 Newton III
    q.append(
        _mcq(
            ["3.2"],
            r"A book rests on a table. Which force forms the Newton's-third-law pair with the "
            r"book's weight?",
            [
                (
                    "The normal force of the table on the book",
                    "Treats the normal force as the reaction to gravity",
                ),
                ("The book's gravitational pull on the Earth", None),
                ("The friction between book and table", "Confuses the pair with a friction force"),
                ("There is no pair", "Believes only some forces have reaction pairs"),
            ],
            0.5,
        )
    )
    q.append(
        _numeric(
            ["3.2", "3.1"],
            r"A $2.0\ \text{kg}$ block touches a $3.0\ \text{kg}$ block on a frictionless table. "
            r"A $10\ \text{N}$ force pushes the $2.0\ \text{kg}$ block into the other. "
            r"What force does the $2.0\ \text{kg}$ block exert on the $3.0\ \text{kg}$ block?",
            3.0 * (10 / (2.0 + 3.0)),
            "N",
            0.7,
        )
    )

    # 3.3 Friction
    q.append(
        _numeric(
            ["3.3"],
            rf"A $10\ \text{{kg}}$ box slides on a horizontal floor with $\mu_k=0.30$. "
            rf"What is the friction force? Take $g={G}\ \text{{m/s}}^2$.",
            0.30 * 10 * G,
            "N",
            -0.2,
        )
    )
    q.append(
        _numeric(
            ["3.3", "3.2"],
            r"A block on a slowly tilting plank starts to slip when the angle reaches "
            r"$30^\circ$. What is the coefficient of static friction?",
            math.tan(math.radians(30)),
            "",
            0.8,
        )
    )

    # 3.4 Circular motion
    q.append(
        _numeric(
            ["3.4"],
            r"A $1000\ \text{kg}$ car takes a curve of radius $50\ \text{m}$ at $15\ \text{m/s}$. "
            r"What centripetal force is needed?",
            1000 * 15**2 / 50,
            "N",
            0.0,
        )
    )
    q.append(
        _numeric(
            ["3.4"],
            r"An object moves at $4.0\ \text{m/s}$ on a circle of radius $2.0\ \text{m}$. "
            r"What is its centripetal acceleration?",
            4.0**2 / 2.0,
            "m/s^2",
            -0.5,
        )
    )

    # 4.1 Work
    q.append(
        _numeric(
            ["4.1"],
            r"A $20\ \text{N}$ force acts at $60^\circ$ to a $5.0\ \text{m}$ displacement. "
            r"How much work does it do?",
            20 * 5.0 * math.cos(math.radians(60)),
            "J",
            -0.2,
        )
    )
    q.append(
        _numeric(
            ["4.1", "4.2"],
            r"Net work of $150\ \text{J}$ is done on a $3.0\ \text{kg}$ object starting from "
            r"rest. What is its final speed?",
            math.sqrt(2 * 150 / 3.0),
            "m/s",
            0.4,
        )
    )

    # 4.2 Kinetic and potential energy
    q.append(
        _numeric(
            ["4.2"],
            r"What is the kinetic energy of a $2.0\ \text{kg}$ object moving at $3.0\ \text{m/s}$?",
            0.5 * 2.0 * 3.0**2,
            "J",
            -1.0,
        )
    )
    q.append(
        _numeric(
            ["4.2"],
            rf"How much gravitational potential energy does a $5.0\ \text{{kg}}$ object gain when "
            rf"lifted $2.0\ \text{{m}}$? Take $g={G}\ \text{{m/s}}^2$.",
            5.0 * G * 2.0,
            "J",
            -0.6,
        )
    )

    # 4.3 Conservation of energy
    q.append(
        _numeric(
            ["4.3", "2.3"],
            rf"A ball is dropped from $20\ \text{{m}}$. Ignoring air resistance, how fast is it "
            rf"moving just before it lands? Take $g={G}\ \text{{m/s}}^2$.",
            math.sqrt(2 * G * 20),
            "m/s",
            0.2,
        )
    )
    q.append(
        _numeric(
            ["4.3"],
            r"A spring ($k=200\ \text{N/m}$) is compressed $0.10\ \text{m}$ and launches a "
            r"$0.50\ \text{kg}$ mass on a frictionless surface. What is the launch speed?",
            math.sqrt(200 * 0.10**2 / 0.50),
            "m/s",
            0.7,
        )
    )

    # 4.4 Power
    q.append(
        _numeric(
            ["4.4", "4.1"],
            rf"A motor lifts a $50\ \text{{kg}}$ load at a constant $2.0\ \text{{m/s}}$. "
            rf"What power does it deliver? Take $g={G}\ \text{{m/s}}^2$.",
            50 * G * 2.0,
            "W",
            0.0,
        )
    )
    q.append(
        _numeric(
            ["4.4", "1.1"],
            r"A $1500\ \text{W}$ heater runs for $2.0\ \text{h}$. How much energy does it use, "
            r"in megajoules?",
            1500 * 2.0 * 3600 / 1e6,
            "MJ",
            -0.2,
        )
    )

    # 5.1 Momentum
    q.append(
        _numeric(
            ["5.1"],
            r"What is the momentum of a $0.15\ \text{kg}$ ball moving at $40\ \text{m/s}$?",
            0.15 * 40,
            "kg m/s",
            -1.0,
        )
    )
    q.append(
        _numeric(
            ["5.1"],
            r"A constant $50\ \text{N}$ force acts for $0.20\ \text{s}$. What impulse does it "
            r"deliver?",
            50 * 0.20,
            "N s",
            -0.7,
        )
    )

    # 5.2 Collisions
    q.append(
        _numeric(
            ["5.2", "5.1"],
            r"A $2.0\ \text{kg}$ cart at $3.0\ \text{m/s}$ hits a $1.0\ \text{kg}$ cart at rest "
            r"and they stick together. What is their common speed afterwards?",
            2.0 * 3.0 / (2.0 + 1.0),
            "m/s",
            0.0,
        )
    )
    q.append(
        _mcq(
            ["5.2", "4.3"],
            r"In a perfectly inelastic collision, which quantity is conserved?",
            [
                ("Momentum, but not kinetic energy", None),
                (
                    "Kinetic energy, but not momentum",
                    "Thinks energy rather than momentum is always conserved",
                ),
                ("Both momentum and kinetic energy", "Believes every collision conserves energy"),
                ("Neither", "Believes a collision with energy loss cannot conserve anything"),
            ],
            0.3,
        )
    )
    return q
