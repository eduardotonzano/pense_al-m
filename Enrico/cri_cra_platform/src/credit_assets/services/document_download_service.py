from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
import unicodedata
from urllib.parse import urlencode
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urljoin, urlsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from credit_assets.collectors.fundosnet_collector import FundosNetCollector
from credit_assets.download_diagnostics import safe_document_filename, safe_filename, sha256_bytes, validate_download
from credit_assets.models.asset import Asset
from credit_assets.repositories.document_version_repository import (
    DocumentVersionRepository,
)
from credit_assets.repositories.document_attempt_repository import (
    DocumentAttemptRepository,
)
from credit_assets.repositories.execution_repository import ExecutionRepository
from credit_assets.utils.fundosnet_normalization import product_type_id


SAMPLE_CATEGORIES = (
    "Termo de Securitização",
    "Aditamento",
    "Informe Mensal",
    "Ata/Edital",
)

CATEGORY_DIRECTORIES = {
    "Termo de Securitização": "termo_securitizacao",
    "Aditamento": "aditamentos",
    "Informe Mensal": "informes_mensais",
    "Ata/Edital": "atas_editais",
}

FORMAT_EXTENSIONS = {
    "PDF": "pdf",
    "XML": "xml",
    "ZIP": "zip",
    "JSON": "json",
    "RTF": "rtf",
    "OLE": "ole",
    "PNG": "png",
    "JPEG": "jpg",
}

MAX_SAMPLE_DOCUMENTS = len(SAMPLE_CATEGORIES)
DEFAULT_MAX_BYTES = 25_000_000


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def infer_sample_category(category: str, document_name: str) -> str | None:
    if category in SAMPLE_CATEGORIES:
        return category
    text = _fold(f"{category} {document_name}")
    if "aditamento" in text:
        return "Aditamento"
    if "termo" in text and ("securitizacao" in text or category == "Outro"):
        return "Termo de Securitização"
    if "informe" in text and "mensal" in text:
        return "Informe Mensal"
    if "edital" in text or "ata" in text or re.search(r"\bago(?:/e)?\b", text):
        return "Ata/Edital"
    return None


def _parse_sort_date(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    value = value.strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%m/%Y",
        "%Y-%m",
    ):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _reference_date_component(value: str | None) -> str:
    if not value:
        return "sem_data"
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        parsed = datetime.strptime(value, "%m/%Y")
        return parsed.strftime("%Y-%m")
    except ValueError:
        return safe_filename(value, fallback="sem_data").removesuffix(".bin")[:24]


def select_sample_documents(
    connection: sqlite3.Connection,
    codigo_cetip: str,
    isin: str,
    categories: Iterable[str] | None = None,
    max_documents: int = MAX_SAMPLE_DOCUMENTS,
) -> dict[str, Any]:
    if max_documents < 1 or max_documents > MAX_SAMPLE_DOCUMENTS:
        raise ValueError(f"max_documents deve estar entre 1 e {MAX_SAMPLE_DOCUMENTS}")
    requested = tuple(categories or SAMPLE_CATEGORIES)
    if not requested or any(category not in SAMPLE_CATEGORIES for category in requested):
        raise ValueError("categoria solicitada fora da amostra D2 aprovada")
    asset = connection.execute(
        """SELECT * FROM assets WHERE codigo_cetip = ? AND isin = ?""",
        (codigo_cetip, isin),
    ).fetchone()
    if asset is None:
        raise ValueError(f"Ativo {codigo_cetip} com ISIN {isin} não encontrado no SQLite")
    rows = list(
        connection.execute(
            """SELECT d.*, a.isin AS asset_isin, a.codigo_cetip AS stored_cetip,
                      COALESCE(v.file_hash, d.file_hash) AS verified_file_hash
               FROM documents d
               JOIN assets a ON a.asset_id = d.asset_id
               LEFT JOIN document_versions v
                 ON v.document_id = d.document_pk
                AND v.is_current = 1
                AND v.validation_status = 'valid'
               WHERE a.isin = ? AND d.source = 'Fundos.NET'
               ORDER BY d.document_pk""",
            (isin,),
        )
    )
    candidates: dict[str, list[sqlite3.Row]] = {category: [] for category in requested}
    excluded: list[dict[str, Any]] = []
    for row in rows:
        category = infer_sample_category(row["category"], row["document_name"])
        if category not in candidates:
            continue
        source_id = str(row["source_document_id"] or "").strip()
        source_url = str(row["source_url"] or "").strip()
        parsed_url = urlsplit(source_url)
        valid_url = parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)
        if not source_id or not valid_url:
            excluded.append({
                "document_id": row["document_pk"],
                "category": category,
                "reason": "source_document_id ausente" if not source_id else "URL inválida",
            })
            continue
        candidates[category].append(row)

    selected = []
    found_categories = []
    for category in requested:
        options = candidates[category]
        if not options:
            continue
        row = max(
            options,
            key=lambda item: (
                bool(item["verified_file_hash"]),
                _parse_sort_date(item["publication_date"] or item["reference_date"]),
                int(item["document_pk"]),
            ),
        )
        found_categories.append(category)
        selected.append({
            "document_id": int(row["document_pk"]),
            "source_document_id": str(row["source_document_id"]),
            "asset_id": int(row["asset_id"]),
            "asset_isin": row["asset_isin"],
            "stored_cetip": row["stored_cetip"],
            "category": category,
            "document_name": row["document_name"],
            "reference_date": row["reference_date"],
            "publication_date": row["publication_date"],
            "source_url": row["source_url"],
            "source": row["source"],
            "source_version": None,
            "current_file_hash": row["verified_file_hash"],
        })
        if len(selected) >= max_documents:
            break
    return {
        "asset_id": int(asset["asset_id"]),
        "codigo_cetip": codigo_cetip,
        "isin": isin,
        "requested_categories": list(requested),
        "found_categories": found_categories,
        "missing_categories": [category for category in requested if category not in found_categories],
        "selected": selected,
        "excluded_candidates": excluded,
        "description_validation": {
            "database_asset_isin_matches": True,
            "live_grade_rows_matched": 0,
            "live_grade_rows_isin_verified": 0,
            "all_selected_rows_verified": False,
        },
    }


def planned_document_path(
    root: str | Path,
    codigo_cetip: str,
    category: str,
    reference_date: str | None,
    source_document_id: str,
    document_name: str,
    file_format: str,
) -> Path:
    if category not in CATEGORY_DIRECTORIES:
        raise ValueError(f"Categoria não permitida para a amostra: {category}")
    cetip_component = re.sub(r"[^A-Za-z0-9_-]", "_", codigo_cetip)
    extension = FORMAT_EXTENSIONS.get(file_format.upper())
    if not extension:
        raise ValueError(f"Formato não suportado para nome de arquivo: {file_format}")
    filename = safe_document_filename(
        _reference_date_component(reference_date),
        source_document_id,
        document_name,
        extension,
    )
    root_path = Path(root).resolve()
    target = (
        root_path / "data" / "documents" / cetip_component
        / CATEGORY_DIRECTORIES[category] / filename
    ).resolve()
    target.relative_to(root_path)
    return target


def planned_document_directory(
    root: str | Path, codigo_cetip: str, category: str
) -> Path:
    if category not in CATEGORY_DIRECTORIES:
        raise ValueError(f"Categoria não permitida para a amostra: {category}")
    cetip_component = re.sub(r"[^A-Za-z0-9_-]", "_", codigo_cetip)
    root_path = Path(root).resolve()
    directory = (
        root_path / "data" / "documents" / cetip_component
        / CATEGORY_DIRECTORIES[category]
    ).resolve()
    directory.relative_to(root_path)
    return directory


class FundosNetBrowserDownloader:
    def __init__(
        self,
        browser_channel: str | None = "msedge",
        headless: bool = True,
        timeout_ms: int = 120_000,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        self.browser_channel = browser_channel
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_bytes = max_bytes

    def download_selected(
        self,
        asset: Asset,
        documents: list[dict[str, Any]],
        temporary_directory: Path,
    ) -> dict[int, dict[str, Any]]:
        collector = FundosNetCollector(
            browser_channel=self.browser_channel,
            headless=self.headless,
            timeout_ms=self.timeout_ms,
        )
        results: dict[int, dict[str, Any]] = {}
        diagnostics: dict[str, Any] = {
            "attempts": [],
            "errors": [],
            "html_diagnostics": [],
            "cookies": [],
            "json_probe": None,
            "ui_events": [],
            "select2": {},
            "native_xhr": [],
            "selectors": {},
            "listar_fundos_payloads": [],
        }
        with sync_playwright() as playwright:
            browser = collector._launch_browser(playwright)
            context = browser.new_context(locale="pt-BR", accept_downloads=True)
            page = context.new_page()
            try:
                page_response = page.goto(
                    collector.BASE_URL + "abrirGerenciadorDocumentosCertificadosCVM",
                    timeout=self.timeout_ms,
                    wait_until="commit",
                )
                if page_response and page_response.status != 200:
                    raise RuntimeError(f"Fundos.NET retornou HTTP {page_response.status}")
                page.wait_for_selector("#tipoFundo", state="attached", timeout=self.timeout_ms)
                page.locator("#tipoFundo").select_option(
                    str(product_type_id(asset.tipo_ativo)), force=True
                )
                page.locator("#tipoFundo").evaluate("el => { $(el).trigger('change'); }")
                administrator = collector._find_administrador(
                    page, context, asset.securitizadora, diagnostics
                )
                if administrator is None:
                    raise RuntimeError("securitizadora não localizada")
                administrator_id = collector._ui_select_administrator(
                    page, asset, administrator, diagnostics
                )
                matches = collector._search_fundos(
                    page, context, asset, administrator_id,
                    product_type_id(asset.tipo_ativo), diagnostics,
                )
                selected_fund = collector._select_match(asset, matches)
                if selected_fund is None or not selected_fund.raw:
                    raise RuntimeError("certificado Café Brasil não localizado inequivocamente")
                id_fundo = collector._ui_select_fund(
                    page, asset, selected_fund, diagnostics
                )
                page_payload = collector._capture_native_document_xhr(
                    page, asset, administrator_id, id_fundo, diagnostics
                )
                pending = {
                    str(document["source_document_id"]): document
                    for document in documents
                }
                rows = list(page_payload.get("data", []))
                current_page = 1
                request_failed: list[dict[str, Any]] = []
                response_events: list[Any] = []
                download_events: list[Any] = []
                page_events: list[str] = []
                response_bodies: dict[int, bytes | str] = {}

                def attach_page(observed_page) -> None:
                    observed_page.on(
                        "requestfailed",
                        lambda request: request_failed.append({
                            "url": self._safe_url(request.url),
                            "failure": request.failure,
                        }),
                    )
                    def collect_response(response) -> None:
                        response_events.append(response)
                        parsed = urlsplit(response.url)
                        if (
                            parsed.path.endswith("/downloadDocumento")
                            and parse_qs(parsed.query).get("id", [""])[-1]
                        ):
                            try:
                                response_bodies[id(response)] = response.body()
                            except Exception as error:
                                response_bodies[id(response)] = (
                                    f"{type(error).__name__}: {error}"
                                )

                    observed_page.on("response", collect_response)
                    observed_page.on(
                        "download",
                        lambda download: download_events.append(download),
                    )

                context.on("page", lambda child: (
                    page_events.append(child.url),
                    attach_page(child),
                ))
                attach_page(page)
                max_pages = max(1, int(page_payload.get("recordsFiltered") or 1) // 10 + 2)
                while pending and current_page <= max_pages:
                    for row in rows:
                        source_id = str(row.get("id") or row.get("idDocumento") or "")
                        document = pending.get(source_id)
                        if document is None:
                            continue
                        description_matches = (
                            asset.isin.upper()
                            in str(row.get("descricaoFundo") or "").upper()
                        )
                        row_result = {
                            "document_id": document["document_id"],
                            "source_document_id": source_id,
                            "live_description": str(row.get("descricaoFundo") or ""),
                            "isin_description_validated": description_matches,
                            "live_type": str(row.get("tipoDocumento") or ""),
                            "live_species": str(row.get("especieDocumento") or ""),
                            "source_version": str(row.get("versao") or "") or None,
                        }
                        if not description_matches:
                            results[document["document_id"]] = {
                                **row_result,
                                "error": "a descrição da linha não corresponde ao ISIN solicitado",
                                "validation_status": "download_failed",
                                "http_status": None,
                                "response_content_type": None,
                                "final_url": None,
                            }
                            del pending[source_id]
                            continue
                        actual_category = infer_sample_category(
                            row_result["live_type"] + " " + row_result["live_species"],
                            row_result["live_type"] or document["document_name"],
                        )
                        if actual_category != document["category"]:
                            results[document["document_id"]] = {
                                **row_result,
                                "error": (
                                    f"categoria da linha ({actual_category}) diverge da "
                                    f"categoria selecionada ({document['category']})"
                                ),
                                "validation_status": "download_failed",
                                "http_status": None,
                                "response_content_type": None,
                                "final_url": None,
                            }
                            del pending[source_id]
                            continue
                        download_action = self._locate_official_download_action(
                            page, source_id
                        )
                        if download_action is None:
                            results[document["document_id"]] = {
                                **row_result,
                                "error": "link oficial Download do Documento ausente na linha",
                                "validation_status": "download_failed",
                                "http_status": None,
                                "response_content_type": None,
                                "final_url": None,
                            }
                            del pending[source_id]
                            continue
                        href = download_action["href"]
                        attempt_started_at = datetime.now(timezone.utc).isoformat()
                        try:
                            capture = self._click_download(
                                page, download_action["locator"], source_id,
                                temporary_directory, response_events,
                                download_events, request_failed, page_events,
                                response_bodies,
                            )
                            results[document["document_id"]] = {
                                **row_result,
                                **capture,
                                "official_url": href,
                                "validation_status": "pending_review",
                                "attempt_started_at": attempt_started_at,
                                "attempt_finished_at": datetime.now(timezone.utc).isoformat(),
                                "http_status": capture["response"].get("status"),
                                "response_content_type": capture["response"].get("content_type"),
                                "final_url": capture["response"].get("final_url")
                                or capture["response"].get("url"),
                            }
                        except Exception as error:
                            results[document["document_id"]] = {
                                **row_result,
                                "official_url": href,
                                "error": f"{type(error).__name__}: {error}",
                                "validation_status": "download_failed",
                                "request_failed": request_failed[-3:],
                                "attempt_started_at": attempt_started_at,
                                "attempt_finished_at": datetime.now(timezone.utc).isoformat(),
                                **self._last_response_for_document(
                                    response_events, source_id
                                ),
                            }
                        del pending[source_id]

                    if not pending:
                        break
                    next_button = page.locator("#tblDocumentosEnviados_next")
                    if (
                        not next_button.count()
                        or "disabled" in (next_button.get_attribute("class") or "")
                    ):
                        break
                    with page.expect_response(
                        lambda response: (
                            "pesquisarGerenciadorDocumentosDados" in response.url
                        ),
                        timeout=self.timeout_ms,
                    ) as response_info:
                        next_button.click(force=True)
                    next_payload = collector._parse_native_response(
                        response_info.value, diagnostics
                    )
                    rows = list(next_payload.get("data", []))
                    current_page += 1
                for source_id, document in pending.items():
                    results[document["document_id"]] = {
                        "document_id": document["document_id"],
                        "source_document_id": source_id,
                        "error": "documento não apareceu na grade paginada",
                        "validation_status": "download_failed",
                        "http_status": None,
                        "response_content_type": None,
                        "final_url": None,
                    }
            except Exception as error:
                for document in documents:
                    if document["document_id"] not in results:
                        results[document["document_id"]] = {
                            "document_id": document["document_id"],
                            "source_document_id": document["source_document_id"],
                            "error": f"{type(error).__name__}: {error}",
                            "validation_status": "download_failed",
                            "http_status": None,
                            "response_content_type": None,
                            "final_url": None,
                        }
            finally:
                context.close()
                browser.close()
        return results

    @staticmethod
    def _last_response_for_document(response_events, source_id: str) -> dict[str, Any]:
        for response in reversed(response_events):
            parsed = urlsplit(response.url)
            if (
                parsed.path.endswith("/downloadDocumento")
                and parse_qs(parsed.query).get("id", [""])[-1] == source_id
            ):
                return {
                    "http_status": response.status,
                    "response_content_type": response.headers.get("content-type", ""),
                    "final_url": FundosNetBrowserDownloader._safe_url(response.url),
                }
        return {
            "http_status": None,
            "response_content_type": None,
            "final_url": None,
        }

    @staticmethod
    def _safe_url(url: str) -> str:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        safe_query = {
            key: values[-1]
            for key, values in query.items()
            if not any(
                marker in key.lower()
                for marker in ("token", "csrf", "auth", "secret", "cookie", "session")
            )
        }
        if not safe_query:
            return parsed._replace(query="", fragment="").geturl()
        return parsed._replace(query=urlencode(safe_query), fragment="").geturl()

    @staticmethod
    def _locate_official_download_action(page, source_id: str):
        for row_locator in page.locator("tr").all():
            anchors = row_locator.locator("a[title='Download do Documento']")
            for index in range(anchors.count()):
                anchor = anchors.nth(index)
                href = anchor.get_attribute("href") or ""
                resolved = urljoin(page.url, href)
                parsed = urlsplit(resolved)
                query = parse_qs(parsed.query)
                if (
                    parsed.hostname == "fnet.bmfbovespa.com.br"
                    and parsed.path.endswith("/downloadDocumento")
                    and query.get("id", [""])[-1] == source_id
                ):
                    return {"href": resolved, "locator": anchor}
        return None

    def _click_download(
        self,
        page,
        locator,
        source_id: str,
        temporary_directory: Path,
        response_events: list[Any],
        download_events: list[Any],
        request_failed: list[dict[str, Any]],
        page_events: list[str],
        response_bodies: dict[int, bytes | str],
    ) -> dict[str, Any]:
        existing_response_count = len(response_events)
        existing_download_count = len(download_events)
        existing_page_count = len(page_events)
        download = None
        try:
            with page.expect_download(
                timeout=min(self.timeout_ms, 15_000)
            ) as download_info:
                locator.click(force=True, timeout=self.timeout_ms)
            download = download_info.value
        except PlaywrightTimeoutError:
            pass
        response = None
        candidates = response_events[existing_response_count:]
        response = next(
            (
                item for item in candidates
                if "downloadDocumento" in urlsplit(item.url).path
                and parse_qs(urlsplit(item.url).query).get("id", [""])[-1] == source_id
            ),
            None,
        )
        if download is None:
            download = next(
                (item for item in download_events[existing_download_count:]),
                None,
            )
        if response is None and download is None:
            raise TimeoutError(
                "clique no link oficial não produziu response nem evento download"
            )

        response_info = None
        if response:
            response_info = {
                "method": response.request.method,
                "url": self._safe_url(response.url),
                "status": response.status,
                "content_type": response.headers.get("content-type", ""),
                "content_disposition": response.headers.get("content-disposition", ""),
                "redirect_count": self._redirect_count(response.request),
            }
        if download:
            filename = safe_filename(download.suggested_filename, "arquivo")
            temporary_path = temporary_directory / f"{source_id}_{filename}"
            download.save_as(str(temporary_path))
            data = temporary_path.read_bytes()
            mechanism = "event_download"
        else:
            response_data = response_bodies.get(id(response))
            if isinstance(response_data, bytes):
                data = response_data
            else:
                try:
                    data = response.body()
                except Exception as error:
                    detail = response_data or f"{type(error).__name__}: {error}"
                    raise RuntimeError(
                        f"resposta sem corpo legível: {detail}"
                    ) from error
            temporary_path = temporary_directory / f"{source_id}_response.bin"
            temporary_path.write_bytes(data)
            mechanism = "binary_response"
        response_info = response_info or {
            "method": None,
            "url": self._safe_url(download.url),
            "status": None,
            "content_type": "",
            "content_disposition": "",
            "redirect_count": 0,
        }
        return {
            "mechanism": mechanism,
            "response": response_info,
            "temporary_path": str(temporary_path),
            "download_name": download.suggested_filename if download else temporary_path.name,
            "popup_count": max(0, len(page_events) - existing_page_count),
            "request_failed": request_failed[-3:],
        }

    @staticmethod
    def _redirect_count(request) -> int:
        count = 0
        previous = request.redirected_from
        while previous is not None:
            count += 1
            previous = previous.redirected_from
        return count


class DocumentDownloadService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        repository: DocumentVersionRepository,
        project_root: str | Path,
        downloader: Any | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        self.connection = connection
        self.repository = repository
        self.project_root = Path(project_root).resolve()
        self.downloader = downloader or FundosNetBrowserDownloader(max_bytes=max_bytes)
        self.max_bytes = max_bytes

    def run(
        self,
        codigo_cetip: str,
        isin: str,
        dry_run: bool = False,
        max_documents: int = MAX_SAMPLE_DOCUMENTS,
        categories: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        run_id = uuid.uuid4().hex
        sample = select_sample_documents(
            self.connection, codigo_cetip, isin, categories, max_documents
        )
        report: dict[str, Any] = {
            "run_id": run_id,
            "asset": {
                "asset_id": sample["asset_id"],
                "codigo_cetip": codigo_cetip,
                "isin": isin,
            },
            "dry_run": dry_run,
            "schema_migration": (
                "document_versions aditiva; índice global UNIQUE de documents.file_hash "
                "substituído por índice não-único, sem remover linhas de documents/assets"
            ),
            "requested_categories": sample["requested_categories"],
            "found_categories": sample["found_categories"],
            "missing_categories": sample["missing_categories"],
            "selected_documents": [],
            "files_downloaded": [],
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "new_version": 0,
            "duplicate_content": 0,
            "failed": 0,
            "files_removed": 0,
            "attempts_recorded": 0,
            "errors": [],
            "description_validation": sample["description_validation"],
            "category_classification_note": (
                "Termo de Securitização e Aditamento não identificados automaticamente; "
                "as categorias persistidas no catálogo são Outro. Nenhuma categoria foi "
                "inventada; requer análise posterior dos nomes e conteúdos."
            ),
        }
        for document in sample["selected"]:
            planned_directory = planned_document_directory(
                self.project_root,
                codigo_cetip,
                document["category"],
            )
            report["selected_documents"].append({
                **document,
                "planned_directory": self._relative_path(planned_directory),
                "planned_filename": safe_document_filename(
                    _reference_date_component(
                        document["reference_date"] or document["publication_date"]
                    ),
                    document["source_document_id"],
                    document["document_name"],
                    "formato",
                ).removesuffix(".formato") + ".<extensao_detectada>",
            })
        if dry_run:
            report["duration_seconds"] = round(time.perf_counter() - started, 4)
            report["files_downloaded_count"] = 0
            return report

        asset_row = self.connection.execute(
            "SELECT * FROM assets WHERE codigo_cetip = ? AND isin = ?",
            (codigo_cetip, isin),
        ).fetchone()
        asset = Asset(
            codigo_cetip=asset_row["codigo_cetip"],
            isin=asset_row["isin"],
            tipo_ativo=asset_row["tipo_ativo"],
            securitizadora=asset_row["securitizadora"],
            cnpj_securitizadora=asset_row["cnpj_securitizadora"],
            emissao=asset_row["emissao"],
            serie=asset_row["serie"],
            devedor=asset_row["devedor"] or "",
            cnpj_devedor=asset_row["cnpj_devedor"] or "",
            asset_id=asset_row["asset_id"],
        )
        execution_repository = ExecutionRepository(self.connection)
        attempt_repository = DocumentAttemptRepository(self.connection)
        execution_repository.start(run_id)
        selected = sample["selected"]
        with tempfile.TemporaryDirectory(prefix="cri-cra-download-") as temporary:
            temp_root = Path(temporary)
            try:
                payloads = self.downloader.download_selected(asset, selected, temp_root)
            except Exception as error:
                payloads = {
                    document["document_id"]: {
                        "error": f"{type(error).__name__}: {error}",
                        "validation_status": "download_failed",
                    }
                    for document in selected
                }
            for document in selected:
                payload = payloads.get(document["document_id"], {
                    "error": "download sem resultado",
                    "validation_status": "download_failed",
                })
                failed_before = report["failed"]
                files_before = len(report["files_downloaded"])
                self._process_document(
                    document, payload, report, temp_root,
                )
                if report["failed"] > failed_before:
                    attempt_status = "failed"
                    matching_error = next(
                        (
                            item["error"]
                            for item in reversed(report["errors"])
                            if item.get("document_id") == document["document_id"]
                        ),
                        "download falhou",
                    )
                else:
                    attempt_status = report["files_downloaded"][-1]["result"]
                    matching_error = None
                response_metadata = payload.get("response") or {}
                attempt_repository.create_attempt(
                    run_id=run_id,
                    asset_id=document["asset_id"],
                    document_id=document["document_id"],
                    source=document.get("source", "Fundos.NET"),
                    started_at=payload.get("attempt_started_at")
                    or datetime.now(timezone.utc).isoformat(),
                    finished_at=payload.get("attempt_finished_at")
                    or datetime.now(timezone.utc).isoformat(),
                    status=attempt_status,
                    http_status=payload.get("http_status")
                    or response_metadata.get("status"),
                    error_message=(
                        self._sanitize_error(matching_error)
                        if matching_error else None
                    ),
                    response_content_type=payload.get("response_content_type")
                    or response_metadata.get("content_type"),
                    final_url=FundosNetBrowserDownloader._safe_url(
                        payload.get("final_url")
                        or response_metadata.get("final_url")
                        or response_metadata.get("url")
                        or payload.get("official_url")
                        or document["source_url"]
                    ),
                )
                self.connection.commit()
                report["attempts_recorded"] += 1
            verified_rows = sum(
                bool(payload.get("isin_description_validated"))
                for payload in payloads.values()
            )
            report["description_validation"].update({
                "live_grade_rows_matched": sum(
                    "live_description" in payload
                    for payload in payloads.values()
                ),
                "live_grade_rows_isin_verified": verified_rows,
                "all_selected_rows_verified": (
                    bool(selected) and verified_rows == len(selected)
                ),
            })
            report["files_removed"] += sum(
                1 for path in temp_root.rglob("*") if path.is_file()
            )
        report["temporary_directory_removed"] = not temp_root.exists()
        report["files_downloaded_count"] = len(report["files_downloaded"])
        report["duration_seconds"] = round(time.perf_counter() - started, 4)
        execution_repository.finish(
            run_id,
            "partial" if report["failed"] else "success",
            report["duration_seconds"],
            1,
            len(selected),
            0,
            report["failed"],
        )
        return report

    def _process_document(
        self,
        document: dict[str, Any],
        payload: dict[str, Any],
        report: dict[str, Any],
        temporary_directory: Path,
    ) -> None:
        document_id = document["document_id"]
        official_url = payload.get("official_url") or document["source_url"]
        common = {
            "document_id": document_id,
            "source_document_id": document["source_document_id"],
            "category": document["category"],
            "official_url": official_url,
            "mechanism": payload.get("mechanism"),
            "isin_description_validated": bool(
                payload.get("isin_description_validated", False)
            ),
            "live_type": payload.get("live_type"),
            "live_species": payload.get("live_species"),
        }
        error = payload.get("error")
        temporary_path = payload.get("temporary_path")
        if error or not temporary_path:
            reason = self._sanitize_error(
                error or "download retornou sem arquivo"
            )
            self._mark_download_failed(document["document_id"])
            report["failed"] += 1
            report["errors"].append({**common, "error": reason})
            return

        temp_file = Path(temporary_path)
        temporary_root = temporary_directory.resolve()
        owns_temp_file = False
        target: Path | None = None
        try:
            temp_file = temp_file.resolve()
            temp_file.relative_to(temporary_root)
            owns_temp_file = True
            if not temp_file.is_file():
                raise FileNotFoundError("arquivo temporário do download não existe")
            file_size = temp_file.stat().st_size
            if file_size == 0:
                self._mark_download_failed(document_id)
                report["failed"] += 1
                report["errors"].append({**common, "error": "empty_file"})
                return
            if file_size > self.max_bytes:
                self._mark_download_failed(document_id)
                report["failed"] += 1
                report["errors"].append({**common, "error": "size_limit_exceeded"})
                return

            data = temp_file.read_bytes()
            content_type = str(payload.get("response", {}).get("content_type") or "")
            validation = validate_download(data, content_type, self.max_bytes)
            validation_status = self._validation_status(validation)
            if validation_status != "valid":
                self._mark_download_failed(document_id)
                report["failed"] += 1
                report["errors"].append({
                    **common,
                    "error": validation_status,
                    "format": validation["format"],
                })
                return

            file_hash = sha256_bytes(data)
            extension = FORMAT_EXTENSIONS[validation["format"]]
            target = planned_document_path(
                self.project_root,
                report["asset"]["codigo_cetip"],
                document["category"],
                document["reference_date"] or document["publication_date"],
                document["source_document_id"],
                document["document_name"],
                validation["format"],
            )
            target = target.with_suffix(f".{extension}")
            if self._is_referenced_path(target):
                version_suffix = re.sub(
                    r"[^A-Za-z0-9_-]", "_", str(payload.get("source_version") or "")
                ).strip("_")
                suffix = (
                    f"_v{version_suffix}_{file_hash[:12]}"
                    if version_suffix
                    else f"_{file_hash[:16]}"
                )
                candidate = target.with_name(
                    f"{target.stem[:60]}{suffix}.{extension}"
                )
                collision = 2
                while self._is_referenced_path(candidate):
                    candidate = target.with_name(
                        f"{target.stem[:55]}{suffix}_{collision}.{extension}"
                    )
                    collision += 1
                target = candidate
            duplicate_rows = self.repository.find_by_hash(file_hash)
            same_document_version = next(
                (row for row in duplicate_rows if row["document_id"] == document_id),
                None,
            )
            if same_document_version:
                if not self._safe_existing_version_file(same_document_version, file_hash):
                    raise RuntimeError(
                        "versão com hash igual já registrada, mas arquivo físico ausente ou divergente"
                    )
                current_version = self.repository.get_current_version(document_id)
                preserved_hash = (
                    current_version["file_hash"] if current_version else file_hash
                )
                self._sync_document_file(document_id, preserved_hash, "downloaded")
                report["unchanged"] += 1
                report["files_downloaded"].append({
                    **common,
                    "result": "unchanged",
                    "format": validation["format"],
                    "size_bytes": file_size,
                    "file_hash": file_hash,
                    "preserved_current_hash": preserved_hash,
                    "local_file_path": same_document_version["local_file_path"],
                    "browser_session_used": True,
                    "requires_browser_session": None,
                })
                return

            shared_file = next(
                (
                    row for row in duplicate_rows
                    if row["validation_status"] == "valid"
                    and self._safe_existing_version_file(row, file_hash)
                ),
                None,
            )
            if shared_file:
                relative_path = str(shared_file["local_file_path"])
                result_type = "duplicate_content"
            else:
                self._atomic_write(target, data)
                relative_path = self._relative_path(target)
                result_type = (
                    "new_version"
                    if any(
                        version["validation_status"] == "valid"
                        for version in self.repository.list_versions(document_id)
                    )
                    else "inserted"
                )

            try:
                self.connection.execute("SAVEPOINT persist_download_version")
                version_id, insert_status = self.repository.create_version(
                    document_id=document_id,
                    file_name=Path(relative_path).name,
                    local_file_path=relative_path,
                    file_format=validation["format"].lower(),
                    file_size_bytes=file_size,
                    file_hash=file_hash,
                    downloaded_at=datetime.now(timezone.utc).isoformat(),
                    source_url=official_url,
                    source_version=payload.get("source_version"),
                    is_current=True,
                    validation_status="valid",
                )
                self.connection.execute(
                    """UPDATE documents SET download_status = 'downloaded', file_hash = ?
                       WHERE document_pk = ?""",
                    (file_hash, document_id),
                )
                if self.connection.execute("SELECT changes()").fetchone()[0] != 1:
                    raise ValueError(f"document_pk inexistente: {document_id}")
                self.connection.execute("RELEASE SAVEPOINT persist_download_version")
            except Exception:
                self.connection.execute("ROLLBACK TO SAVEPOINT persist_download_version")
                self.connection.execute("RELEASE SAVEPOINT persist_download_version")
                if not shared_file:
                    self._remove_if_unreferenced(target)
                raise

            report["inserted"] += int(insert_status == "inserted")
            if result_type == "new_version":
                report["new_version"] += 1
            elif result_type == "duplicate_content":
                report["duplicate_content"] += 1
            archive_members = (
                self._zip_members(
                    target if not shared_file
                    else self._path_for(shared_file["local_file_path"])
                )
                if validation["format"] == "ZIP"
                else []
            )
            report["files_downloaded"].append({
                **common,
                "result": result_type,
                "version_id": version_id,
                "format": validation["format"],
                "size_bytes": file_size,
                "file_hash": file_hash,
                "local_file_path": relative_path,
                "source_version": payload.get("source_version"),
                "redirect_count": payload.get("response", {}).get("redirect_count", 0),
                "browser_session_used": True,
                "requires_browser_session": None,
                "archive_members": archive_members,
                "temporary_removed_by_context": True,
            })
        except Exception as error:
            if target is not None:
                self._remove_if_unreferenced(target)
            self._mark_download_failed(document_id)
            report["failed"] += 1
            report["errors"].append({**common, "error": f"{type(error).__name__}: {error}"})
        finally:
            if owns_temp_file and temp_file.exists():
                temp_file.unlink()
                report["files_removed"] += 1

    @staticmethod
    def _validation_status(validation: dict[str, Any]) -> str:
        if validation["is_html"]:
            return "html_instead_of_file"
        if not validation["size_bytes"]:
            return "empty_file"
        if not validation["within_limit"]:
            return "size_limit_exceeded"
        if not validation["accepted"]:
            return "invalid_format"
        return "valid"

    def _mark_download_failed(self, document_id: int) -> None:
        current = self.repository.get_current_version(document_id)
        document = self.connection.execute(
            "SELECT file_hash FROM documents WHERE document_pk = ?",
            (document_id,),
        ).fetchone()
        if current is None and document and not document["file_hash"]:
            self.connection.execute(
                "UPDATE documents SET download_status = 'failed' WHERE document_pk = ?",
                (document_id,),
            )
        self.connection.commit()

    @staticmethod
    def _sanitize_error(error: str) -> str:
        return re.sub(
            r"([?&][^=&]*(?:token|csrf|auth|secret|cookie|session)[^=]*=)[^&\s]+",
            r"\1[REDACTED]",
            str(error),
            flags=re.IGNORECASE,
        )[:2000]

    def _sync_document_file(self, document_id: int, file_hash: str, status: str) -> None:
        self.connection.execute(
            "UPDATE documents SET download_status = ?, file_hash = ? WHERE document_pk = ?",
            (status, file_hash, document_id),
        )
        self.connection.commit()

    def _atomic_write(self, destination: Path, data: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        resolved_root = (self.project_root / "data" / "documents").resolve()
        resolved_destination = destination.resolve()
        resolved_destination.relative_to(resolved_root)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def _safe_existing_version_file(self, row, expected_hash: str) -> bool:
        try:
            path = self._path_for(row["local_file_path"])
            root = (self.project_root / "data" / "documents").resolve()
            path.relative_to(root)
            return path.is_file() and sha256_bytes(path.read_bytes()) == expected_hash
        except (OSError, ValueError, TypeError):
            return False

    def _path_for(self, local_path: str) -> Path:
        candidate = Path(local_path)
        resolved = (
            candidate if candidate.is_absolute()
            else self.project_root / candidate
        ).resolve()
        return resolved

    def _relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root).as_posix()

    def _remove_if_unreferenced(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            relative = self._relative_path(path)
        except ValueError:
            return
        referenced = self.connection.execute(
            "SELECT 1 FROM document_versions WHERE local_file_path = ? LIMIT 1",
            (relative,),
        ).fetchone()
        if not referenced:
            path.unlink()

    def _is_referenced_path(self, path: Path) -> bool:
        try:
            relative = self._relative_path(path)
        except ValueError:
            return False
        return self.connection.execute(
            "SELECT 1 FROM document_versions WHERE local_file_path = ? LIMIT 1",
            (relative,),
        ).fetchone() is not None

    @staticmethod
    def _zip_members(path: Path) -> list[str]:
        try:
            with zipfile.ZipFile(path) as archive:
                return archive.namelist()
        except (OSError, zipfile.BadZipFile):
            return []
