"""Validated box dimensions, five independent challenge settings and mechanisms."""
from dataclasses import dataclass
from .collection import (COLLECTIONS, FIGURES, SCENES, EXPRESSIONS,
                         COLLECTION_OPTIONS)

FACES = ("Frontal", "Derecha", "Trasera", "Izquierda", "Tapa")
DIFFICULTIES = ("Fácil", "Medio", "Difícil")
THEMES = {"Ninguno": "", "Huellas": "paw", "Estrellas": "star", "Relámpagos": "bolt"}
PUZZLES = {
    "cerrojo_rueda": {"name": "Cerrojo deslizante con rueda de bloqueo", "implemented": True},
    "laberinto": {"name": "Laberinto mecánico con cursor cautivo", "implemented": True},
    "secuencia": {"name": "Compuerta lineal: bajar y deslizar", "implemented": True},
    "cifrado": {"name": "Cifrado mecánico de anillos", "implemented": True},
}
# These are geometry/game-step profiles, not calibrated player difficulty.
DIAL_MARKS = {"Fácil": 2, "Medio": 4, "Difícil": 8}
ARM_HEIGHT = {"Fácil": 7.5, "Medio": 9.0, "Difícil": 10.5}
RELEASE_TRAVEL = 20.0
SIDE_MECHANISM_FIELDS = (
    "mecanismo_frontal","mecanismo_derecha",
    "mecanismo_trasera","mecanismo_izquierda",
)
MECHANISM_FOR_FACE = dict(zip(FACES[:4],SIDE_MECHANISM_FIELDS))


def difficulty_detail(mechanism, difficulty):
    """Describe the rule/step count represented by one face's setting."""
    if difficulty not in DIFFICULTIES:
        raise ValueError("Dificultad desconocida: %s" % difficulty)
    if mechanism == "laberinto":
        from .maze_lock import path_for
        _path, turns = path_for(difficulty)
        return "%d giros" % turns
    if mechanism == "cifrado":
        from .cipher_lock import cipher_profile
        profile = cipher_profile(difficulty)
        return "%d anillos · %d posiciones" % (profile["rings"],profile["positions"])
    if mechanism == "secuencia":
        return "bajar 12 mm · deslizar 20 mm"
    return "%d posiciones" % DIAL_MARKS[difficulty]


@dataclass(frozen=True)
class PuzzleConfig:
    width: float = 170.0
    depth: float = 160.0
    height: float = 95.0
    wall: float = 5.5
    floor: float = 4.0
    clearance: float = 0.35
    theme: str = "Huellas"
    frontal: str = "Fácil"
    derecha: str = "Medio"
    trasera: str = "Fácil"
    izquierda: str = "Medio"
    tapa: str = "Medio"
    mecanismo_frontal: str = "cerrojo_rueda"
    mecanismo_derecha: str = "cerrojo_rueda"
    mecanismo_trasera: str = "cerrojo_rueda"
    mecanismo_izquierda: str = "cerrojo_rueda"
    collection: str = "Ninguna"
    figure: str = "Ninguna"
    scene: str = "Ninguno"
    expression: str = "Feliz"
    figure_height: float = 30.0

    def face_difficulty(self, face):
        return getattr(self, {"Frontal":"frontal", "Derecha":"derecha",
                              "Trasera":"trasera", "Izquierda":"izquierda",
                              "Tapa":"tapa"}[face])

    def face_mechanism(self, face):
        if face not in MECHANISM_FOR_FACE:
            raise ValueError("La leva superior es el quinto mecanismo fijo.")
        return getattr(self, MECHANISM_FOR_FACE[face])

    @property
    def difficulties(self):
        return tuple(self.face_difficulty(face) for face in FACES)

    @property
    def prize_interior(self):
        """Conservative approximate envelope, not a figurine fit certification."""
        return (self.width-2*self.wall-8,
                self.depth-2*self.wall-8,
                self.height-self.floor-23)

    def validate(self):
        if not 150 <= self.width <= 320 or not 150 <= self.depth <= 320:
            raise ValueError("Ancho y fondo deben estar entre 150 y 320 mm (espacio para mecanismos).")
        if not 75 <= self.height <= 240:
            raise ValueError("Alto permitido: 75–240 mm.")
        if not 5 <= self.wall <= 9 or not 3 <= self.floor <= self.wall:
            raise ValueError("Pared: 5–9 mm; suelo: 3 mm hasta el grosor de pared.")
        if not 0.2 <= self.clearance <= 0.65:
            raise ValueError("Holgura nominal: 0.20–0.65 mm (requiere calibración física).")
        if self.collection not in COLLECTIONS:
            raise ValueError("Colección desconocida.")
        if self.figure not in FIGURES or self.scene not in SCENES:
            raise ValueError("Figura o escenario desconocido.")
        if self.expression not in EXPRESSIONS or not 25 <= self.figure_height <= 40:
            raise ValueError("Expresión o altura de personaje inválida (25–40 mm).")
        valid_figures,valid_scenes=COLLECTION_OPTIONS[self.collection]
        if self.figure not in valid_figures or self.scene not in valid_scenes:
            raise ValueError("El personaje o escenario no pertenece a la colección %s." % self.collection)
        if self.collection != "Ninguna" and self.theme != "Ninguno":
            raise ValueError("Las colecciones incluyen relieves: usa motivo Ninguno.")
        if self.theme not in THEMES:
            raise ValueError("Motivo decorativo desconocido.")
        if any(value not in DIFFICULTIES for value in self.difficulties):
            raise ValueError("Cada una de las cinco caras necesita una dificultad válida.")
        for face in FACES[:4]:
            key=self.face_mechanism(face)
            if key not in PUZZLES or not PUZZLES[key]["implemented"]:
                raise ValueError("Mecanismo lateral no implementado: %s" % key)
        return self


def can_open(released_sides, top_released):
    """Intended five-lock AND invariant, not a dynamics simulation."""
    if len(released_sides) != 4:
        raise ValueError("Se requieren los estados de los cuatro laterales.")
    return bool(top_released and all(released_sides))
