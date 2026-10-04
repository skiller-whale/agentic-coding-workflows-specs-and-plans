"""Shows the city map in the terminal. Run with `python app.py`; press q to quit."""

from rich.text import Text
from textual.app import App
from textual.widgets import Footer, Header, Static

from city import BUILDING, PARK, ROAD, City

# How each kind of cell is drawn: (character, style).
CELL_STYLES = {
    ROAD: (" ", "on grey30"),
    BUILDING: ("▒", "tan on grey19"),
    PARK: ("♣", "green on dark_green"),
}


def draw(city):
    text = Text()
    for row in city.rows:
        for cell in row:
            text.append(*CELL_STYLES[cell])
        text.append("\n")
    return text


class CityApp(App):
    TITLE = "City"
    CSS = """
    Screen { align: center middle; }
    #map { width: auto; height: auto; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self):
        yield Header()
        yield Static(draw(City.load()), id="map")
        yield Footer()


if __name__ == "__main__":
    CityApp().run()
