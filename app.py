"""
Bundle of Authorities (BOA) Autobot - FastAPI Local Web Application.
"""
import os
import secrets
import shutil
from typing import List, Dict, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

from boa_core.models import (
    AuthorityItem, CaseMetadata, GroupConfig, ParseResponse,
    AuthorityCategory, RetrievalStatus
)
from boa_core.extractor import extract_docx_footnotes
from boa_core.resolver import resolve_citations
from boa_core.classifier import classify_all
from boa_core.sorter import sort_and_group_authorities, get_default_group_configs
from boa_core.retriever import retrieve_all
from boa_core.generator import build_bundle_of_authorities
from boa_core.config import PORT, HOST, LOCAL_MODEL_PORT, LOCAL_MODEL_NAME
from boa_core.local_llm import LocalLLMClient

app = FastAPI(title="Bundle of Authorities Autobot", version="1.0.0")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMP_DIR = os.path.join(BASE_DIR, "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Bundle of Authorities Autobot</h1><p>UI loading...</p>"


@app.get("/trailer", response_class=HTMLResponse)
async def serve_trailer():
    trailer_path = os.path.join(STATIC_DIR, "trailer.html")
    if os.path.exists(trailer_path):
        with open(trailer_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Trailer loading...</h1>"


@app.post("/api/upload", response_model=ParseResponse)
async def upload_docx(
    file: UploadFile = File(...),
    include_sentence_context: bool = Form(False)
):
    """Uploads a .docx draft, extracts footnotes, resolves cross-references, and classifies."""
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    # A random name, never the uploaded one: a crafted file name could otherwise write outside TEMP_DIR
    temp_path = os.path.join(TEMP_DIR, f"upload_{secrets.token_hex(8)}.docx")
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Extract footnotes & filter factual evidence
        footnotes = extract_docx_footnotes(temp_path, include_sentence_context=include_sentence_context)
        filtered_evidence = [fn for fn in footnotes if not fn.is_authority]

        # 2. Resolve cross-references and aggregate pinpoints
        authorities = resolve_citations(footnotes)

        # 3. Classify into 7 default groups
        classify_all(authorities)

        # 4. Default group configs
        group_configs = get_default_group_configs()

        return ParseResponse(
            total_footnotes=len(footnotes),
            filtered_evidence_count=len(filtered_evidence),
            authorities=authorities,
            group_configs=group_configs,
            detected_metadata=CaseMetadata()
        )
    finally:
        _remove(temp_path)


@app.get("/api/load-example", response_model=ParseResponse)
async def load_example_memo(include_sentence_context: bool = False):
    """Loads the bundled example memo for instant 1-click testing."""
    example_path = os.path.join(
        BASE_DIR,
        "Example docs for BOA",
        "Example memo with a certain order for list of authorities that can be used for BOAs (but no BOA).docx"
    )
    if not os.path.exists(example_path):
        # Fallback to realistic demo authorities covering all categories for public repo users
        from boa_core.models import AuthorityCategory, AuthorityItem, RetrievalStatus
        sample_authorities = [
            AuthorityItem(
                id="auth-sg-1",
                raw_citation="Quoine Pte Ltd v B2C2 Ltd [2020] SGCA(I) 02 at [63]-[64]",
                title="Quoine Pte Ltd v B2C2 Ltd",
                citation="[2020] SGCA(I) 02",
                year=2020,
                category=AuthorityCategory.SINGAPORE_CASES,
                pinpoints=["[63]", "[64]"],
                source_footnote_ids=[1, 5, 12],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-sg-2",
                raw_citation="Low Yung Chyuan v Management Corporation Strata Title Plan No 2351 [2019] SGSTB 3 at [42]",
                title="Low Yung Chyuan v Management Corporation Strata Title Plan No 2351",
                citation="[2019] SGSTB 3",
                year=2019,
                category=AuthorityCategory.SINGAPORE_CASES,
                pinpoints=["[42]"],
                source_footnote_ids=[3],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-stat-1",
                raw_citation="Building Maintenance and Strata Management Act 2004 (2020 Rev Ed) ss 32, 33(1)",
                title="Building Maintenance and Strata Management Act 2004",
                citation="(2020 Rev Ed)",
                year=2004,
                category=AuthorityCategory.SINGAPORE_STATUTES,
                pinpoints=["s 32", "s 33(1)"],
                source_footnote_ids=[7, 18],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-stat-2",
                raw_citation="Arbitration Act 2001 (2020 Rev Ed) s 30(1)(c)",
                title="Arbitration Act 2001",
                citation="(2020 Rev Ed)",
                year=2001,
                category=AuthorityCategory.SINGAPORE_STATUTES,
                pinpoints=["s 30(1)(c)"],
                source_footnote_ids=[22],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-reg-1",
                raw_citation="Arbitration Rules of the Singapore International Arbitration Centre (SIAC Rules 2016) Rule 28.2",
                title="Arbitration Rules of the Singapore International Arbitration Centre",
                citation="(SIAC Rules 2016)",
                year=2016,
                category=AuthorityCategory.REGULATIONS,
                pinpoints=["Rule 28.2"],
                source_footnote_ids=[29],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-fc-1",
                raw_citation="Triple Point Technology, Inc v PTT Public Co Ltd [2021] UKSC 29 at [35]",
                title="Triple Point Technology, Inc v PTT Public Co Ltd",
                citation="[2021] UKSC 29",
                year=2021,
                category=AuthorityCategory.FOREIGN_CASES,
                pinpoints=["[35]"],
                source_footnote_ids=[44],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-fstat-1",
                raw_citation="Arbitration Act 1996 (c 23) (UK) s 68",
                title="Arbitration Act 1996 (UK)",
                citation="(c 23)",
                year=1996,
                category=AuthorityCategory.FOREIGN_STATUTES,
                pinpoints=["s 68"],
                source_footnote_ids=[51],
                retrieval_status=RetrievalStatus.PENDING
            ),
            AuthorityItem(
                id="auth-sec-1",
                raw_citation="Hugh Beale, Chitty on Contracts (Sweet & Maxwell, 34th Ed, 2021) at paras 24-001 to 24-015",
                title="Chitty on Contracts (Sweet & Maxwell, 34th Ed, 2021)",
                citation="34th Ed, 2021",
                year=2021,
                category=AuthorityCategory.SECONDARY_SOURCES,
                pinpoints=["paras 24-001 - 24-015"],
                source_footnote_ids=[65],
                retrieval_status=RetrievalStatus.PENDING
            )
        ]
        return ParseResponse(
            total_footnotes=104,
            filtered_evidence_count=22,
            authorities=sample_authorities,
            group_configs=get_default_group_configs(),
            detected_metadata=CaseMetadata(
                court_name="IN THE STATE COURTS OF THE REPUBLIC OF SINGAPORE",
                case_number="DC/OA XXX/YYYY\nDC/SUM XXXX/YYYY",
                matter_description="In the matter of sections [X] and [Y] of the [Name of Act]",
                claimant_name="[NAME OF CLAIMANT]",
                claimant_uen="[UEN]",
                respondent_name="[NAME OF RESPONDENT]",
                respondent_uen="[UEN]",
                document_title="CLAIMANT'S BUNDLE OF AUTHORITIES",
                dated_date="Dated this [day] day of [month] [year]",
                claimant_solicitors="SOLICITORS FOR THE CLAIMANT\n[NAME OF SOLICITORS]\n[NAME OF LAW PARTNERSHIP]\n[ADDRESS]",
                respondent_solicitors="SOLICITORS FOR THE RESPONDENT\n[NAME OF SOLICITORS]\n[NAME OF LAW PARTNERSHIP]\n[ADDRESS]"
            )
        )

    footnotes = extract_docx_footnotes(example_path, include_sentence_context=include_sentence_context)
    filtered_evidence = [fn for fn in footnotes if not fn.is_authority]
    authorities = resolve_citations(footnotes)
    classify_all(authorities)
    group_configs = get_default_group_configs()

    # Pre-populate realistic metadata from the example BOA
    meta = CaseMetadata(
        court_name="IN THE STATE COURTS OF THE REPUBLIC OF SINGAPORE",
        case_number="DC/OA XXX/YYYY\nDC/SUM XXXX/YYYY",
        matter_description="In the matter of sections [X] and [Y] of the [Name of Act]",
        claimant_name="[NAME OF CLAIMANT]",
        claimant_uen="[UEN]",
        respondent_name="[NAME OF RESPONDENT]",
        respondent_uen="[UEN]",
        document_title="CLAIMANT'S BUNDLE OF AUTHORITIES",
        dated_date="Dated this [day] day of [month] [year]",
        claimant_solicitors="SOLICITORS FOR THE CLAIMANT\n[NAME OF SOLICITORS]\n[NAME OF LAW PARTNERSHIP]\n[ADDRESS]",
        respondent_solicitors="SOLICITORS FOR THE RESPONDENT\n[NAME OF SOLICITORS]\n[NAME OF LAW PARTNERSHIP]\n[ADDRESS]"
    )

    return ParseResponse(
        total_footnotes=len(footnotes),
        filtered_evidence_count=len(filtered_evidence),
        authorities=authorities,
        group_configs=group_configs,
        detected_metadata=meta
    )


class RetrieveRequest(BaseModel):
    authorities: List[AuthorityItem]
    use_live_network: bool = True


@app.post("/api/retrieve")
async def retrieve_authorities(req: RetrieveRequest):
    """Checks Singapore judgments on eLitigation; every other authority is marked for a placeholder sheet."""
    updated = retrieve_all(req.authorities, use_live_network=req.use_live_network)
    return {"authorities": updated}


class GenerateRequest(BaseModel):
    metadata: CaseMetadata
    authorities: List[AuthorityItem]
    custom_order: Optional[List[str]] = None
    merged_groups: Optional[Dict[str, str]] = None


@app.post("/api/generate")
async def generate_boa_docx(req: GenerateRequest):
    """Sorts alphabetically within groups and generates final .docx Bundle of Authorities."""
    # 1. Sort and group authorities deterministically
    grouped = sort_and_group_authorities(
        req.authorities,
        custom_order=req.custom_order,
        merged_groups=req.merged_groups
    )

    # 2. Build .docx
    out_file = os.path.join(TEMP_DIR, f"Bundle_of_Authorities_{secrets.token_hex(8)}.docx")
    try:
        build_bundle_of_authorities(req.metadata, grouped, out_file)
    except Exception:
        _remove(out_file)
        raise

    if not os.path.exists(out_file):
        raise HTTPException(status_code=500, detail="Failed to generate BOA document.")

    filename = f"{req.metadata.document_title.replace(' ', '_')}.docx"
    # The bundle is deleted once it has been sent
    return FileResponse(
        out_file,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
        background=BackgroundTask(_remove, out_file)
    )


@app.get("/api/model-status")
async def get_model_status():
    """Checks the health and status of the local model endpoint."""
    client = LocalLLMClient()
    return client.check_health()


if __name__ == "__main__":
    import uvicorn
    print(f"\n========================================================")
    print(f"  Bundle of Authorities Autobot")
    print(f"  Web Server:   http://{HOST}:{PORT}")
    print(f"  Local LLM:    Port {LOCAL_MODEL_PORT} ({LOCAL_MODEL_NAME})")
    print(f"========================================================\n")
    uvicorn.run(app, host=HOST, port=PORT)
