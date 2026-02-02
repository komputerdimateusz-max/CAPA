from __future__ import annotations


def test_ui_settings_page(client):
    response = client.get("/ui/settings")

    assert response.status_code == 200


def test_ui_analyses_page(client, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPA_DATA_DIR", str(tmp_path))

    response = client.get("/ui/analyses")

    assert response.status_code == 200
