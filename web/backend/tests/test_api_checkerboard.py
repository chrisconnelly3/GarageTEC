"""The printable calibration board. Shipping it removes the most common
calibration failure: a board off the internet with the wrong square count, or
printed scaled so every measured distance is wrong."""


def test_checkerboard_is_svg_sized_in_real_millimetres(client):
    r = client.get("/api/calibration/checkerboard.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    # Physical units are the whole point: mm prints at true size, px does not.
    assert 'width="270.000mm"' in r.text
    assert 'height="207.000mm"' in r.text


def test_default_board_fits_a4_and_has_the_right_square_count(client):
    r = client.get("/api/calibration/checkerboard.svg")
    # 10x7 squares alternating -> 35 black, plus one white background rect.
    assert r.text.count("<rect") == 36
    # The label must state INNER corners (9x6), which is what OpenCV counts and
    # what the app's cols/rows fields expect.
    assert "9 x 6" in r.text


def test_label_warns_against_fit_to_page(client):
    """Scaling the print silently corrupts every downstream measurement."""
    text = client.get("/api/calibration/checkerboard.svg").text
    assert "100%" in text
    assert "fit to" in text.lower()


def test_square_size_is_honoured(client):
    r = client.get("/api/calibration/checkerboard.svg?square_mm=30&cols=6&rows=4")
    assert 'width="200.000mm"' in r.text     # 6*30 + 2*10 margin
    assert "5 x 3" in r.text                 # inner corners


def test_absurd_input_is_clamped_not_rejected(client):
    """A silly query must still yield a usable board, never a 500 or a
    poster-sized print job."""
    r = client.get("/api/calibration/checkerboard.svg?square_mm=9999&cols=999&rows=0")
    assert r.status_code == 200
    assert 'width="1220.000mm"' in r.text    # 20 cols * 60mm + margins
