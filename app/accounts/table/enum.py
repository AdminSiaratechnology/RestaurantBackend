from enum import Enum


class TableShape(str, Enum):
    rectangular = "rectangular"
    round = "round"
    square = "square"
    oval = "oval"


class TableStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    reserved = "reserved"