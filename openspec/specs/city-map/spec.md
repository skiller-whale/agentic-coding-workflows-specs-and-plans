# city-map Specification

## Purpose
Show a fixed map of a city block in the terminal.

## Requirements

### Requirement: Fixed map
The app SHALL read the city from `city_map.txt`, where each character is one cell: `.` is road, `#` is a building and `T` is park. Cell (0, 0) is the top-left corner.

#### Scenario: Top-left corner
- **WHEN** the map is loaded
- **THEN** cell (0, 0) is a road

### Requirement: Draw the map
The app SHALL draw every cell of the map, with roads, buildings and parks each in their own colour.

#### Scenario: Start the app
- **WHEN** someone runs `python app.py`
- **THEN** the whole map is shown, and `q` quits
