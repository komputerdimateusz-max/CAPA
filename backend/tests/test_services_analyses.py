from __future__ import annotations

from app.services import analyses as analyses_service


def test_create_analysis_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPA_DATA_DIR", str(tmp_path))

    created = analyses_service.create_analysis(
        analysis_type="5WHY",
        title="Packaging defect",
        description="Root cause drill-down",
        champion="Alex",
    )

    assert created["analysis_id"].startswith("5WHY-")
    rows, total = analyses_service.list_analyses_page(page=1, page_size=10)

    assert total == 1
    assert rows[0]["title"] == "Packaging defect"
