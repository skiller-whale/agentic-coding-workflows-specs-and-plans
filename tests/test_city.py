from city import City


def test_the_map_is_a_rectangle():
    city = City.load()
    assert all(len(row) == city.width for row in city.rows)


def test_the_top_left_corner_is_a_road():
    assert City.load().is_road(0, 0)
