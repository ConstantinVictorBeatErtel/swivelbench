"""Reproducible SEC EDGAR acquisition and Company Facts normalization.

The fetcher is intentionally stdlib-only. It keeps a content-addressed raw
cache, records every URL and response hash, sleeps between requests, and can
rebuild normalized facts without network access.
"""
from __future__ import annotations

import json
import gzip
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .provenance import append_jsonl, sha256_bytes, sha256_file
from .schemas import FilingSnapshot, SecFact

SEC_BASE = "https://data.sec.gov"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"
DEFAULT_USER_AGENT = (
    "SwivelBench/0.1 (public benchmark content acquisition; "
    "see repository metadata for contact)"
)

COMPANIES: dict[str, dict[str, str]] = {
    "ADBE": {"company_id": "PUB-ADBE", "cik": "0000796343", "split": "train"},
    "ORCL": {"company_id": "PUB-ORCL", "cik": "0001341439", "split": "train"},
    "COST": {"company_id": "PUB-COST", "cik": "0000909832", "split": "train"},
    "WMT": {"company_id": "PUB-WMT", "cik": "0000104169", "split": "train"},
    "DAL": {"company_id": "PUB-DAL", "cik": "0000027904", "split": "train"},
    "UPS": {"company_id": "PUB-UPS", "cik": "0001090727", "split": "train"},
    "CAT": {"company_id": "PUB-CAT", "cik": "0000018230", "split": "train"},
    "DE": {"company_id": "PUB-DE", "cik": "0000315189", "split": "train"},
    "NEE": {"company_id": "PUB-NEE", "cik": "0000753308", "split": "train"},
    "DUK": {"company_id": "PUB-DUK", "cik": "0001326160", "split": "train"},
    "HCA": {"company_id": "PUB-HCA", "cik": "0000860731", "split": "train"},
    "CVS": {"company_id": "PUB-CVS", "cik": "0000064803", "split": "train"},
    "KO": {"company_id": "PUB-KO", "cik": "0000021344", "split": "validation"},
    "NUE": {"company_id": "PUB-NUE", "cik": "0000073309", "split": "validation"},
    "VZ": {"company_id": "PUB-VZ", "cik": "0000732712", "split": "validation"},
    "F": {"company_id": "PUB-F", "cik": "0000037996", "split": "validation"},
    "PEP": {"company_id": "PUB-PEP", "cik": "0000077476", "split": "test"},
    "DOW": {"company_id": "PUB-DOW", "cik": "0001751788", "split": "test"},
    "T": {"company_id": "PUB-T", "cik": "0000732717", "split": "test"},
    "GM": {"company_id": "PUB-GM", "cik": "0001467858", "split": "test"},
}

FACT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet", "Revenues", "SalesRevenueGoodsNet",
    ),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "assets": ("Assets",),
    "short_term_debt": (
        "ShortTermBorrowings", "ShortTermDebt", "LongTermDebtCurrent",
    ),
    "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "interest_expense": (
        "InterestExpenseNonOperating", "InterestExpenseDebt",
    ),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
    ),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "depreciation_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    ),
    "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
}


@dataclass(frozen=True)
class FetchRecord:
    url: str
    local_path: str
    sha256: str
    bytes: int
    fetched_at: str
    status: str = "ok"
    error: str = ""


class SecClient:
    def __init__(self, root: Path, *, user_agent: str | None = None,
                 min_interval: float = 0.25, timeout: float = 45.0,
                 retries: int = 4):
        self.root = Path(root)
        self.raw = self.root / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent or os.environ.get(
            "SWIVELBENCH_SEC_USER_AGENT", DEFAULT_USER_AGENT)
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = retries
        self._last_request = 0.0
        self.records_path = self.root / "fetch_records.jsonl"
        try:
            import certifi
            self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:  # pragma: no cover - platform fallback
            self._ssl_context = ssl.create_default_context()

    def _path_for_url(self, url: str) -> Path:
        return self.raw / sha256_bytes(url.encode())[:2] / sha256_bytes(url.encode())

    def fetch(self, url: str) -> tuple[bytes, Path]:
        path = self._path_for_url(url)
        if path.is_file():
            cached = path.read_bytes()
            decoded = _decode_content(cached)
            if decoded != cached:
                path.write_bytes(decoded)
            return decoded, path
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(
                url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"})
            self._last_request = time.monotonic()
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout, context=self._ssl_context
                ) as response:
                    data = _decode_content(response.read())
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(path)
                append_jsonl(self.records_path, asdict(FetchRecord(
                    url=url, local_path=str(path), sha256=sha256_bytes(data),
                    bytes=len(data), fetched_at=date.today().isoformat())))
                return data, path
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(30.0, 2.0 ** attempt))
        raise RuntimeError(f"SEC fetch failed after retries: {url}: {last_error}")


def _json_bytes(data: bytes, url: str) -> dict[str, Any]:
    try:
        value = json.loads(_decode_content(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"SEC response was not JSON: {url}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"SEC JSON root was not an object: {url}")
    return value


def _decode_content(data: bytes) -> bytes:
    """Normalize SEC gzip responses so cached artifacts are JSON-readable."""
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def _dash_accession(value: str) -> str:
    return value.replace("-", "")


def _selected_filings(submissions: dict[str, Any], cutoff: str) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    rows: list[dict[str, Any]] = []
    fields = list(recent)
    for i, form in enumerate(recent.get("form", [])):
        if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A"}:
            continue
        filed = recent.get("filingDate", [""] * len(recent["form"]))[i]
        if filed and filed > cutoff:
            continue
        row = {field: recent[field][i] for field in fields if i < len(recent[field])}
        rows.append(row)
    rows.sort(key=lambda row: (row.get("filingDate", ""), row.get("accessionNumber", "")), reverse=True)
    annual = [row for row in rows if row.get("form") in {"10-K", "10-K/A"}][:3]
    quarterly = [row for row in rows if row.get("form") in {"10-Q", "10-Q/A"}][:2]
    return sorted(annual + quarterly, key=lambda row: (row.get("filingDate", ""), row.get("accessionNumber", "")))


def acquire_company(client: SecClient, ticker: str, *, cutoff: str,
                    out_root: Path) -> dict[str, Any]:
    if ticker not in COMPANIES:
        raise KeyError(ticker)
    meta = COMPANIES[ticker]
    cik = meta["cik"]
    submissions_url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    facts_url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    submissions_data, submissions_path = client.fetch(submissions_url)
    facts_data, facts_path = client.fetch(facts_url)
    submissions = _json_bytes(submissions_data, submissions_url)
    facts = _json_bytes(facts_data, facts_url)
    company_root = Path(out_root) / ticker
    company_root.mkdir(parents=True, exist_ok=True)
    (company_root / "submissions.json").write_bytes(submissions_data)
    (company_root / "companyfacts.json").write_bytes(facts_data)
    filings: list[dict[str, Any]] = []
    for row in _selected_filings(submissions, cutoff):
        accession = row.get("accessionNumber", "")
        accession_path = _dash_accession(accession)
        primary = row.get("primaryDocument", "")
        archive_url = f"{ARCHIVE_BASE}/{int(cik)}/{accession_path}/{primary}"
        document_data, document_path = client.fetch(archive_url)
        local = company_root / "filings" / accession / primary
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(document_data)
        index_url = f"{ARCHIVE_BASE}/{int(cik)}/{accession_path}/index.json"
        index_data, index_path = client.fetch(index_url)
        index_local = company_root / "filings" / accession / "index.json"
        index_local.write_bytes(index_data)
        snapshot = FilingSnapshot(
            company_id=meta["company_id"], ticker=ticker, cik=cik,
            accession=accession, form=row.get("form", ""),
            filed_date=row.get("filingDate", ""),
            period_end=row.get("reportDate", ""), primary_document=primary,
            primary_sha256=sha256_bytes(document_data),
            companyfacts_sha256=sha256_bytes(facts_data),
            source_url=archive_url, local_artifact=str(local),
            index_artifact=str(index_local),
        )
        filings.append(snapshot.to_dict())
    manifest = {
        "schema": "swivelbench.sec-company.v1",
        "company_id": meta["company_id"], "ticker": ticker, "cik": cik,
        "split": meta["split"], "cutoff": cutoff,
        "submissions_url": submissions_url,
        "submissions_artifact": str(submissions_path),
        "submissions_sha256": sha256_bytes(submissions_data),
        "companyfacts_url": facts_url,
        "companyfacts_artifact": str(facts_path),
        "companyfacts_sha256": sha256_bytes(facts_data),
        "filings": filings,
    }
    (company_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _fact_units(concept: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    units = concept.get("units") or {}
    rows: list[tuple[str, dict[str, Any]]] = []
    for unit, values in units.items():
        if isinstance(values, list):
            rows.extend((unit, row) for row in values if isinstance(row, dict))
    return rows


def _pick_fact(facts: dict[str, Any], filing: dict[str, Any], metric: str,
               company_id: str) -> SecFact | None:
    taxonomy = "us-gaap"
    concepts = facts.get("facts", {}).get(taxonomy, {})
    target_form = filing["form"]
    target_accn = _dash_accession(filing["accession"])
    target_end = filing.get("period_end", "")
    for concept_name in FACT_CANDIDATES[metric]:
        concept = concepts.get(concept_name)
        if not concept:
            continue
        candidates: list[tuple[str, dict[str, Any]]] = []
        for unit, row in _fact_units(concept):
            accn = _dash_accession(str(row.get("accn", "")))
            form = row.get("form", "")
            if accn == target_accn and form == target_form:
                candidates.append((unit, row))
        if not candidates:
            continue
        candidates.sort(key=lambda item: (item[1].get("filed", ""), item[1].get("end", "")), reverse=True)
        unit, row = candidates[0]
        value = row.get("val")
        if not isinstance(value, (int, float, str)):
            continue
        context = "|".join(str(row.get(k, "")) for k in ("start", "end", "frame", "fp", "form", "accn"))
        return SecFact(
            fact_id=f"{company_id}:{metric}:{row.get('accn')}:{concept_name}",
            company_id=company_id, taxonomy=taxonomy, concept=concept_name,
            value=value, unit=unit, start_date=row.get("start"),
            end_date=row.get("end"), instant_date=row.get("instant"),
            form=form, filed_date=row.get("filed", ""),
            accession=row.get("accn", ""), source_url=filing["source_url"],
            source_artifact=filing["local_artifact"],
            context_hash=sha256_bytes(context.encode())[:16],
        )
    return None


def normalize_company(company_manifest: dict[str, Any], *, root: Path) -> list[SecFact]:
    ticker = company_manifest["ticker"]
    facts_path = Path(root) / ticker / "companyfacts.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    out: list[SecFact] = []
    for filing in company_manifest.get("filings", []):
        for metric in FACT_CANDIDATES:
            fact = _pick_fact(facts, filing, metric, company_manifest["company_id"])
            if fact:
                out.append(fact)
    return out


def acquire_all(*, root: Path, cutoff: str, tickers: list[str] | None = None,
                user_agent: str | None = None) -> dict[str, Any]:
    root = Path(root)
    client = SecClient(root, user_agent=user_agent)
    selected = tickers or list(COMPANIES)
    manifests = []
    facts_path = root / "normalized" / "sec_facts.jsonl"
    facts_path.unlink(missing_ok=True)
    for ticker in selected:
        manifest = acquire_company(client, ticker, cutoff=cutoff, out_root=root)
        manifests.append(manifest)
        for fact in normalize_company(manifest, root=root):
            append_jsonl(facts_path, fact)
    summary = {
        "schema": "swivelbench.sec-release.v1",
        "cutoff": cutoff,
        "tickers": selected,
        "companies": len(manifests),
        "filings": sum(len(m["filings"]) for m in manifests),
        "normalized_facts": len(facts_path.read_text(encoding="utf-8").splitlines()) if facts_path.exists() else 0,
        "raw_root": str(root / "raw"),
        "normalized_facts_path": str(facts_path),
    }
    (root / "release-manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def verify_offline(root: Path) -> dict[str, Any]:
    root = Path(root)
    issues: list[str] = []
    manifests = []
    for path in sorted(root.glob("*/manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests.append(manifest)
        for key in ("submissions_artifact", "companyfacts_artifact"):
            artifact = Path(manifest[key])
            if not artifact.is_file():
                issues.append(f"missing {key}: {artifact}")
            elif sha256_file(artifact) != manifest.get(
                "submissions_sha256" if key == "submissions_artifact" else "companyfacts_sha256"
            ):
                issues.append(f"hash mismatch: {artifact}")
        for filing in manifest.get("filings", []):
            for key in ("local_artifact", "index_artifact"):
                artifact = Path(filing[key])
                if not artifact.is_file():
                    issues.append(f"missing {key}: {artifact}")
            if Path(filing["local_artifact"]).is_file():
                actual = sha256_file(Path(filing["local_artifact"]))
                if actual != filing["primary_sha256"]:
                    issues.append(f"hash mismatch: {filing['local_artifact']}")
    result = {"ok": not issues, "companies": len(manifests), "issues": issues}
    (root / "offline-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def restore_artifact(artifact: Path, root: Path) -> dict[str, Any]:
    """Restore a release tar.zst into an explicitly supplied SEC root."""
    artifact = Path(artifact).resolve()
    root = Path(root).resolve()
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    root.mkdir(parents=True, exist_ok=True)
    decompressor = subprocess.Popen(["zstd", "-d", "-c", str(artifact)], stdout=subprocess.PIPE)
    extractor = subprocess.Popen(["tar", "-xf", "-", "-C", str(root)], stdin=decompressor.stdout)
    assert decompressor.stdout is not None
    decompressor.stdout.close()
    extractor.wait()
    decompressor.wait()
    if extractor.returncode or decompressor.returncode:
        raise subprocess.CalledProcessError(extractor.returncode or decompressor.returncode, "restore")
    return {"artifact": str(artifact), "root": str(root), "restored": True}


def package_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    """Package the exact acquired SEC tree for offline release distribution."""
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    if not (root / "release-manifest.json").is_file():
        raise FileNotFoundError(root / "release-manifest.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "--use-compress-program=zstd", "-cf", str(artifact), "-C", str(root), "."],
        check=True,
    )
    result = {
        "artifact": artifact.name, "artifact_path": str(artifact), "sha256": sha256_file(artifact),
        "bytes": artifact.stat().st_size, "root": str(root),
    }
    (root / "artifact-manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
