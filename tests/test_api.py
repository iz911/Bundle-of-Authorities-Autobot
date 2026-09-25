import io
import os
import zipfile
import xml.etree.ElementTree as ET

import docx
from fastapi.testclient import TestClient

from app import TEMP_DIR, app
from conftest import requires_memo

client = TestClient(app)

GROUP_ORDER = [
    "Singapore Cases",
    "Singapore Statutes",
    "Regulations / Statutory Instruments",
    "Foreign Cases",
    "Foreign Statutes",
    "Secondary Sources",
    "Miscellaneous",
]
MERGE_FOREIGN = {"Foreign Statutes": "Foreign Authorities", "Foreign Cases": "Foreign Authorities"}


def docx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content), "r") as z:
        assert "word/document.xml" in z.namelist()
        root = ET.fromstring(z.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "".join(node.text for node in root.findall(".//w:t", ns) if node.text)


def retrieve_and_generate(data: dict) -> str:
    authorities = data["authorities"]

    ret_resp = client.post("/api/retrieve", json={"authorities": authorities[:10], "use_live_network": False})
    assert ret_resp.status_code == 200
    assert len(ret_resp.json()["authorities"]) == min(10, len(authorities))

    gen_resp = client.post("/api/generate", json={
        "metadata": data["detected_metadata"],
        "authorities": authorities,
        "custom_order": GROUP_ORDER,
        "merged_groups": MERGE_FOREIGN,
    })
    assert gen_resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in gen_resp.headers["content-type"]
    return docx_text(gen_resp.content)


def a_docx() -> bytes:
    document = docx.Document()
    document.add_paragraph("A draft with no footnotes.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_api_serve_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Bundle of Authorities Autobot" in response.text


def test_sample_authorities_generate_a_bundle():
    response = client.get("/api/load-example?include_sentence_context=false")
    assert response.status_code == 200
    data = response.json()
    assert len(data["authorities"]) > 0

    text = retrieve_and_generate(data)
    assert "CLAIMANT'S BUNDLE OF AUTHORITIES" in text
    assert "INDEX TO CLAIMANT'S BUNDLE OF AUTHORITIES" in text
    assert "Foreign Authorities" in text


@requires_memo
def test_api_load_example_and_generate():
    response = client.get("/api/load-example?include_sentence_context=false")
    assert response.status_code == 200
    data = response.json()
    assert data["total_footnotes"] > 90
    assert data["filtered_evidence_count"] > 30
    assert len(data["authorities"]) > 20

    text = retrieve_and_generate(data)
    assert "CLAIMANT'S BUNDLE OF AUTHORITIES" in text
    assert "Foreign Authorities" in text


def test_upload_rejects_other_file_types():
    response = client.post("/api/upload", files={"file": ("draft.pdf", b"%PDF-1.4", "application/pdf")})
    assert response.status_code == 400


def test_upload_file_name_cannot_leave_the_temp_folder():
    outside = os.path.join(os.path.dirname(TEMP_DIR), "escaped.docx")
    response = client.post("/api/upload", files={"file": ("../escaped.docx", a_docx(), "application/octet-stream")})
    assert response.status_code == 200
    assert not os.path.exists(outside)


def test_nothing_is_left_behind():
    before = set(os.listdir(TEMP_DIR))
    client.post("/api/upload", files={"file": ("draft.docx", a_docx(), "application/octet-stream")})
    retrieve_and_generate(client.get("/api/load-example").json())
    assert set(os.listdir(TEMP_DIR)) == before
