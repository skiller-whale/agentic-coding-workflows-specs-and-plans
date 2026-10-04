"""The city: a fixed grid of roads, buildings and parks, read from city_map.txt."""

from pathlib import Path

ROAD = "."
BUILDING = "#"
PARK = "T"

MAP_PATH = Path(__file__).with_name("city_map.txt")


class City:
    def __init__(self, rows):
        self.rows = rows
        self.width = len(rows[0])
        self.height = len(rows)

    @classmethod
    def load(cls, path=MAP_PATH):
        return cls(path.read_text().splitlines())

    def cell(self, x, y):
        return self.rows[y][x]

    def is_road(self, x, y):
        return self.cell(x, y) == ROAD
