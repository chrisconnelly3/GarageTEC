def test_serves_existing_file(client):
    (client.media_dir / "swings").mkdir()
    f = client.media_dir / "swings" / "annotated.mp4"
    f.write_bytes(b"\x00\x01fakevideo")
    r = client.get("/media/swings/annotated.mp4")
    assert r.status_code == 200
    assert r.content == b"\x00\x01fakevideo"


def test_missing_file_404(client):
    assert client.get("/media/nope.mp4").status_code == 404


def test_rejects_parent_traversal(client, tmp_path):
    # a secret outside the media root
    secret = client.media_dir.parent / "secret.txt"
    secret.write_text("top secret")
    r = client.get("/media/../secret.txt")
    assert r.status_code in (400, 404)
    assert "top secret" not in r.text


def test_rejects_encoded_traversal(client):
    r = client.get("/media/%2e%2e/secret.txt")
    assert r.status_code in (400, 404)
