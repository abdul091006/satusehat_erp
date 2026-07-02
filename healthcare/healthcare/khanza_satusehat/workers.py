﻿import copy
import hashlib
import re
import time
import uuid

import frappe
import requests
from frappe import _

from .constants import (
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_FAILED_PERMANENT,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_PENDING,
    IMPORT_STATUS_PROCESSING,
    LOG_DOCTYPE,
    MAX_ATTEMPTS,
    QUEUE_DOCTYPE,
    REVIEW_STATUS_PENDING,
    VALIDATION_STATUS_ERROR,
    VALIDATION_STATUS_VALID,
    VALIDATION_STATUS_WARNING,
    SATUSEHAT_HTTP_TIMEOUT_SECONDS,
    SEND_BATCH_LIMIT,
    SEND_TIME_BUDGET_SECONDS,
    SYNC_STATUS_WAITING,
)
from .document_events import target_docstatus_label
from .healthcare_import import import_khanza_to_healthcare_doc
from .logs import _append_log, _safe_append_review_parquet
from .persistence import _safe_store_satusehat_resource_id
from .satusehat_client import (
    _endpoint_for,
    _find_existing_satusehat_resource,
    _is_duplicate_response,
    _normalize_fhir_for_satusehat,
    _resource_url,
    _response_resource_id,
    _satusehat_headers,
)
from .utils import _as_dict, _json_dumps, _now, _parse_names, _should_retry

RESOURCE_SEND_ORDER = {
    "Encounter": 10,
    "Medication": 20,
    "Condition": 30,
    "Procedure": 40,
    "ClinicalImpression": 50,
    "Composition": 55,
    "ServiceRequest": 60,
    "Specimen": 70,
    "Observation": 80,
    "DiagnosticReport": 90,
    "MedicationRequest": 100,
    "MedicationDispense": 110,
    "MedicationStatement": 120,
    "CarePlan": 130,
    "QuestionnaireResponse": 140,
    "AllergyIntolerance": 150,
    "Immunization": 160,
}

SYNC_STATUS_ORDER = {
    "sent": 0,
    "processing": 1,
    "pending": 2,
    SYNC_STATUS_WAITING: 3,
    "failed": 4,
    "failed_permanent": 5,
}


def _resource_sort_key(doc):
    resource_order = RESOURCE_SEND_ORDER.get(doc.resource_type, 999)
    if doc.resource_type == "Encounter" and (doc.method or "").upper() == "PUT":
        resource_order = 900

    return (
        resource_order,
        doc.creation,
        doc.name,
    )

REFERENCE_RESOURCE_TYPES = {
    "Encounter",
    "Condition",
    "Observation",
    "Procedure",
    "ServiceRequest",
    "Specimen",
    "Medication",
    "MedicationRequest",
    "MedicationDispense",
    "MedicationStatement",
    "DiagnosticReport",
    "CarePlan",
    "ClinicalImpression",
    "QuestionnaireResponse",
    "AllergyIntolerance",
    "Immunization",
    "Composition",
}


class DependencyNotReady(Exception):
    pass


def _queue_meta_has(fieldname):
    return frappe.get_meta(QUEUE_DOCTYPE).has_field(fieldname)


def _filter_queue_updates(values):
    return {
        fieldname: value
        for fieldname, value in values.items()
        if _queue_meta_has(fieldname)
    }


def _target_doc_for_queue(queue_doc):
    target_doctype = getattr(queue_doc, "target_doctype", None)
    target_docname = getattr(queue_doc, "target_docname", None)
    if target_doctype and target_docname and frappe.db.exists(target_doctype, target_docname):
        return frappe.get_doc(target_doctype, target_docname)
    return None


def _technical_review_validation(queue_doc, fhir, target_doc):
    issues = []
    warnings = []
    resource_type = fhir.get("resourceType") or fhir.get("resource_type")

    if not resource_type:
        issues.append("Payload tidak punya resourceType/resource_type.")

    if not target_doc:
        issues.append("Target ERPNext document belum terbentuk.")
    elif int(getattr(target_doc, "docstatus", 0) or 0) == 2:
        issues.append(f"Target ERPNext document {target_doc.doctype}/{target_doc.name} sudah Cancelled.")

    for reference in _reference_values(fhir):
        if not isinstance(reference, str) or "/" not in reference:
            continue

        resource_type, local_id = reference.split("/", 1)
        if resource_type not in REFERENCE_RESOURCE_TYPES:
            continue

        row = (
            _find_dependency_queue(resource_type, local_id)
            or _find_dependency_queue_from_context(resource_type, fhir)
        )
        if not row:
            warnings.append(f"Dependency {reference} belum punya sync record lokal.")

    if issues:
        return VALIDATION_STATUS_ERROR, "\n".join(list(dict.fromkeys(issues + warnings)))
    if warnings:
        return VALIDATION_STATUS_WARNING, "\n".join(list(dict.fromkeys(warnings)))
    return VALIDATION_STATUS_VALID, "Validasi teknis ringan lolos."


def _row_value(row_or_doc, fieldname, default=None):
    if hasattr(row_or_doc, "get"):
        return row_or_doc.get(fieldname, default)
    return getattr(row_or_doc, fieldname, default)


def _queue_target_docstatus(row_or_doc):
    target_doctype = _row_value(row_or_doc, "target_doctype")
    target_docname = _row_value(row_or_doc, "target_docname")

    if target_doctype and target_docname and frappe.db.exists(target_doctype, target_docname):
        status = target_docstatus_label(
            frappe.db.get_value(target_doctype, target_docname, "docstatus")
        )
    else:
        status = _row_value(row_or_doc, "target_docstatus") or "Draft"

    queue_name = _row_value(row_or_doc, "name")
    if queue_name and frappe.get_meta(QUEUE_DOCTYPE).has_field("target_docstatus"):
        frappe.db.set_value(
            QUEUE_DOCTYPE,
            queue_name,
            "target_docstatus",
            status,
            update_modified=False,
        )
    return status


def _is_queue_target_submitted(row_or_doc):
    return _queue_target_docstatus(row_or_doc) == "Submitted"


def _mark_waiting_submission(doc, status=None):
    status = status or _queue_target_docstatus(doc)
    message = (
        f"Target ERPNext document {getattr(doc, 'target_doctype', None) or 'target document'}/"
        f"{getattr(doc, 'target_docname', None) or '-'} masih {status}. "
        "Submit target document before SatuSehat send."
    )
    updates = _filter_queue_updates(
        {
            "target_docstatus": status,
            "approval_status": "Pending",
            "approved_by": None,
            "approved_at": None,
            "sync_status": "pending",
            "last_review_event_at": _now(),
            "error_message": message,
        }
    )
    frappe.db.set_value(
        QUEUE_DOCTYPE,
        doc.name,
        updates,
        update_modified=True,
    )
    frappe.db.commit()
    return message


def _mark_waiting_dependency(doc, message):
    updates = _filter_queue_updates(
        {
            "sync_status": SYNC_STATUS_WAITING,
            "last_attempt_at": None,
            "last_review_event_at": _now(),
            "error_message": message,
        }
    )
    frappe.db.set_value(
        QUEUE_DOCTYPE,
        doc.name,
        updates,
        update_modified=True,
    )
    frappe.db.commit()
    fresh_doc = frappe.get_doc(QUEUE_DOCTYPE, doc.name)
    _safe_append_review_parquet(fresh_doc, "waiting_dependency", extra={"message": message})
    return message


def release_waiting_dependencies(limit=500):
    rows = frappe.get_all(
        QUEUE_DOCTYPE,
        filters={
            "import_status": IMPORT_STATUS_IMPORTED,
            "approval_status": "Approved",
            "target_docstatus": "Submitted",
            "sync_status": SYNC_STATUS_WAITING,
        },
        fields=["name"],
        order_by="modified asc",
        limit_page_length=int(limit or 500),
    )

    released = []
    refreshed = False
    for row in rows:
        if not frappe.db.exists(QUEUE_DOCTYPE, row.name):
            continue

        doc = frappe.get_doc(QUEUE_DOCTYPE, row.name)
        message = _current_dependency_wait_message(doc)
        if message:
            if message and message != getattr(doc, "error_message", None):
                frappe.db.set_value(
                    QUEUE_DOCTYPE,
                    doc.name,
                    "error_message",
                    message,
                    update_modified=False,
                )
                refreshed = True
            continue

        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            {
                "sync_status": "pending",
                "last_attempt_at": None,
                "error_message": None,
            },
            update_modified=True,
        )
        released.append(doc.name)

    if released or refreshed:
        frappe.db.commit()

    return released

_RESOURCE_EXISTS_CACHE = {}


def _satusehat_resource_exists(resource_type, resource_id):
    if not resource_type or not resource_id:
        return False

    cache_key = (resource_type, resource_id)
    if cache_key in _RESOURCE_EXISTS_CACHE:
        return _RESOURCE_EXISTS_CACHE[cache_key]

    try:
        response = requests.get(
            _resource_url(resource_type, resource_id),
            headers=_satusehat_headers(),
            timeout=SATUSEHAT_HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise DependencyNotReady(
            f"Belum bisa validasi dependency {resource_type}/{resource_id}: {error}"
        )

    if response.ok:
        _RESOURCE_EXISTS_CACHE[cache_key] = True
        return True

    if response.status_code in (400, 404):
        _RESOURCE_EXISTS_CACHE[cache_key] = False
        return False

    raise frappe.ValidationError(
        f"Dependency check HTTP {response.status_code}: {response.text or ''}"
    )


def _is_reference_not_found_response(response_text):
    response_text = response_text or ""
    if "reference_not_found" in response_text:
        return True
    if "reference target(s) not found" in response_text:
        return True
    return False


def _reset_missing_reference_targets(fhir, response_text):
    response_text = response_text or ""
    targets = re.findall(r"([A-Za-z]+(?:[A-Za-z]+)?)/([A-Za-z0-9][A-Za-z0-9\\-\\.]{5,})", response_text)

    for resource_type, local_id in targets:
        if resource_type not in REFERENCE_RESOURCE_TYPES:
            continue

        row = (
            _find_dependency_queue(resource_type, local_id)
            or _find_dependency_queue_from_context(resource_type, fhir)
        )
        if not row:
            continue

        _reset_dependency_for_retry(
            row,
            (
                f"SATUSEHAT menolak child resource karena dependency tidak ditemukan: "
                f"{resource_type}/{local_id}. Parent dijadwalkan ulang."
            ),
            clear_resource_id=row.get("sync_status") == "sent",
        )


def _find_sent_resource_id(resource_type, local_id):
    row = _find_dependency_queue(resource_type, local_id)
    if row and row.get("sync_status") == "sent" and row.get("satusehat_resource_id"):
        return row.get("satusehat_resource_id")

    return None

def _first_coding(value):
    if not isinstance(value, dict):
        return {}
    coding = value.get("coding") or []
    return coding[0] if coding else {}

def _primary_code_parts(fhir):
    codeable = (
        fhir.get("code")
        or fhir.get("vaccineCode")
        or fhir.get("medicationCodeableConcept")
    )
    coding = _first_coding(codeable)
    system = coding.get("system")
    code = coding.get("code")
    return system, code

def _find_sent_resource_id_by_code(resource_type, fhir):
    system, code = _primary_code_parts(fhir)
    if not code:
        return None

    like_code = f"%{code}%"
    if system:
        like_system = f"%{system}%"
        rows = frappe.db.sql(
            f"""
            SELECT satusehat_resource_id
            FROM `tab{QUEUE_DOCTYPE}`
            WHERE resource_type = %s
              AND sync_status = 'sent'
              AND satusehat_resource_id IS NOT NULL
              AND fhir_payload LIKE %s
              AND fhir_payload LIKE %s
            ORDER BY modified DESC
            LIMIT 1
            """,
            (resource_type, like_code, like_system),
        )
    else:
        rows = frappe.db.sql(
            f"""
            SELECT satusehat_resource_id
            FROM `tab{QUEUE_DOCTYPE}`
            WHERE resource_type = %s
              AND sync_status = 'sent'
              AND satusehat_resource_id IS NOT NULL
              AND fhir_payload LIKE %s
            ORDER BY modified DESC
            LIMIT 1
            """,
            (resource_type, like_code),
        )

    return rows[0][0] if rows else None

def _find_dependency_queue(resource_type, local_id):
    if not local_id:
        return None

    candidates = []

    # contoh local_id: Encounter-2026/05/22/940001
    candidates.append(local_id)

    # contoh local_id: 2026/05/22/940001
    if not local_id.startswith(f"{resource_type}-"):
        candidates.append(f"{resource_type}-{local_id}")

    for external_id in candidates:
        row = _get_dependency_queue_row({"resource_type": resource_type, "external_id": external_id})
        if row:
            return row

    ack_found = _find_dependency_queue_by_ack_id(resource_type, local_id)
    if ack_found:
        return ack_found

    found = frappe.db.sql(
        f"""
        SELECT
          name,
          external_id,
          sync_status,
          satusehat_resource_id,
          target_doctype,
          target_docname,
          target_docstatus
        FROM `tab{QUEUE_DOCTYPE}`
        WHERE resource_type = %s
          AND (
              external_id = %s
              OR external_id LIKE %s
              OR fhir_payload LIKE %s
              OR payload LIKE %s
          )
        ORDER BY
          CASE sync_status
            WHEN 'sent' THEN 0
            WHEN 'processing' THEN 1
            WHEN 'pending' THEN 2
            WHEN 'waiting' THEN 3
            WHEN 'failed' THEN 4
            WHEN 'failed_permanent' THEN 5
            ELSE 9
          END,
          modified DESC
        LIMIT 1
        """,
        (resource_type, local_id, f"%{local_id}%", f"%{local_id}%", f"%{local_id}%"),
        as_dict=True,
    )

    if found:
        return found[0]

    return None

def _get_dependency_queue_row(filters):
    rows = frappe.get_all(
        QUEUE_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "external_id",
            "sync_status",
            "satusehat_resource_id",
            "target_doctype",
            "target_docname",
            "target_docstatus",
        ],
        order_by="modified desc",
        limit_page_length=20,
    )
    rows.sort(key=lambda row: (SYNC_STATUS_ORDER.get(row.get("sync_status"), 9), row.get("name")))
    return rows[0] if rows else None

def _find_sent_resource_id_by_ack_id(resource_type, ack_id):
    row = _find_dependency_queue_by_ack_id(resource_type, ack_id)
    if row and row.get("sync_status") == "sent":
        return row.get("satusehat_resource_id")
    return None

def _find_dependency_queue_by_ack_id(resource_type, ack_id):
    if not ack_id:
        return None

    rows = frappe.get_all(
        QUEUE_DOCTYPE,
        filters={
            "resource_type": resource_type,
        },
        fields=[
            "name",
            "external_id",
            "sync_status",
            "satusehat_resource_id",
            "target_doctype",
            "target_docname",
            "target_docstatus",
        ],
        order_by="modified desc",
        limit_page_length=1000,
    )
    rows.sort(key=lambda row: (SYNC_STATUS_ORDER.get(row.get("sync_status"), 9), row.get("name")))
    for row in rows:
        if _java_name_uuid(f"khanza-erpnext-fhir:{row.external_id}") == ack_id:
            return row
    return None

def _java_name_uuid(text):
    digest = bytearray(hashlib.md5((text or "").encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _extract_no_rawat_candidates(value):
    text = _json_dumps(value)
    return list(dict.fromkeys(re.findall(r"\d{4}/\d{2}/\d{2}/\d{6}", text)))

def _find_dependency_queue_from_context(resource_type, context_fhir):
    if resource_type != "Encounter":
        return None

    for no_rawat in _extract_no_rawat_candidates(context_fhir):
        row = _find_dependency_queue("Encounter", no_rawat)
        if row:
            return row

    return None

def _reset_dependency_for_retry(row, reason, clear_resource_id=False):
    if not row or not row.get("name"):
        return

    updates = {
        "sync_status": "pending",
        "last_attempt_at": None,
        "error_message": reason,
    }
    if clear_resource_id and frappe.get_meta(QUEUE_DOCTYPE).has_field("satusehat_resource_id"):
        updates["satusehat_resource_id"] = None

    frappe.db.set_value(
        QUEUE_DOCTYPE,
        row.get("name"),
        updates,
        update_modified=True,
    )

def _verified_dependency_resource_id(row, resource_type, local_id):
    resource_id = row.get("satusehat_resource_id")
    if not resource_id:
        return None

    if _satusehat_resource_exists(resource_type, resource_id):
        return resource_id

    _reset_dependency_for_retry(
        row,
        (
            f"ID SATUSEHAT yang tersimpan tidak ditemukan saat dipakai sebagai dependency: "
            f"{resource_type}/{resource_id}. Referensi lokal: {resource_type}/{local_id}"
        ),
        clear_resource_id=True,
    )
    frappe.db.commit()
    raise DependencyNotReady(
        f"Dependency {resource_type}/{local_id} punya ID lama {resource_id}, "
        "tapi ID itu tidak ada di SATUSEHAT. Parent di-reset untuk dikirim ulang."
    )

def _resolve_reference_value(reference, context_fhir=None):
    if not isinstance(reference, str) or "/" not in reference:
        return reference

    resource_type, local_id = reference.split("/", 1)

    if resource_type not in REFERENCE_RESOURCE_TYPES:
        return reference

    dependency_row = (
        _find_dependency_queue(resource_type, local_id)
        or _find_dependency_queue_from_context(resource_type, context_fhir)
    )
    if dependency_row:
        if dependency_row.get("sync_status") == "sent":
            satusehat_id = _verified_dependency_resource_id(dependency_row, resource_type, local_id)
            if satusehat_id:
                return f"{resource_type}/{satusehat_id}"

        target_status = _queue_target_docstatus(dependency_row)
        if target_status != "Submitted":
            raise DependencyNotReady(
                f"Dependency belum siap: {reference}. Parent sync record {dependency_row.get('name')} "
                f"target document masih {target_status}. Submit parent dulu."
            )

        if dependency_row.get("sync_status") == "failed":
            _reset_dependency_for_retry(
                dependency_row,
                f"Dibutuhkan oleh resource lain sebagai dependency {reference}; dijadwalkan ulang.",
            )
            frappe.db.commit()

        raise DependencyNotReady(
            f"Dependency belum siap: {reference}. Parent sync record {dependency_row.get('name')} "
            f"statusnya {dependency_row.get('sync_status') or 'unknown'}."
        )

    if _satusehat_resource_exists(resource_type, local_id):
        return reference

    raise DependencyNotReady(
        f"Dependency belum siap: {reference} belum punya parent sync record/satusehat_resource_id di ERPNext/SATUSEHAT"
    )


def _dependency_message_list(errors):
    messages = []
    seen = set()
    for error in errors:
        message = str(error).strip()
        if not message or message in seen:
            continue
        seen.add(message)
        messages.append(message)
    return messages


def _format_dependency_errors(errors):
    messages = _dependency_message_list(errors)
    if not messages:
        return ""
    if len(messages) == 1:
        return messages[0]
    return "Beberapa dependency belum siap:\n- " + "\n- ".join(messages)


def _current_dependency_wait_message(doc):
    try:
        fhir = _as_dict(getattr(doc, "fhir_payload", None))
        if not fhir:
            return None
        _resolve_fhir_references(copy.deepcopy(fhir))
    except DependencyNotReady as error:
        return str(error)
    return None


def _resolve_fhir_references(value, context_fhir=None):
    if context_fhir is None:
        context_fhir = value

    errors = []

    def walk(current):
        if isinstance(current, dict):
            if isinstance(current.get("reference"), str):
                try:
                    current["reference"] = _resolve_reference_value(current["reference"], context_fhir)
                except DependencyNotReady as error:
                    errors.append(error)

            for child in current.values():
                walk(child)

        elif isinstance(current, list):
            for child in current:
                walk(child)

    walk(value)

    if errors:
        raise DependencyNotReady(_format_dependency_errors(errors))

    return value


def recover_stuck_processing(minutes=30):
    """
    Recovery untuk sync record yang nyangkut di status processing.

    Penyebab umum:
    - worker mati/restart saat sedang kirim
    - request timeout
    - exception terjadi sebelum status sempat diubah ke sent/failed

    Setelah lewat X menit, status processing dianggap stuck dan diubah ke failed
    supaya bisa diproses ulang oleh send_approved_queue().
    """
    minutes = int(minutes or 30)

    frappe.db.sql(
        f"""
        UPDATE `tab{QUEUE_DOCTYPE}`
        SET
            sync_status = 'failed',
            error_message = CONCAT(
                COALESCE(error_message, ''),
                CASE
                    WHEN error_message IS NULL OR error_message = ''
                    THEN ''
                    ELSE '\\n'
                END,
                'Recovered from stuck processing status'
            ),
            modified = NOW()
        WHERE sync_status = 'processing'
          AND last_attempt_at IS NOT NULL
          AND TIMESTAMPDIFF(MINUTE, last_attempt_at, NOW()) >= %s
        """,
        (minutes,),
    )
    frappe.db.commit()


def recover_dependency_failures():
    frappe.db.sql(
        f"""
        UPDATE `tab{QUEUE_DOCTYPE}`
        SET
            sync_status = %s,
            last_attempt_at = NULL,
            modified = NOW()
        WHERE import_status = 'imported'
          AND approval_status = 'Approved'
          AND sync_status = 'failed'
          AND attempts < %s
          AND (
              error_message LIKE '%%reference_not_found%%'
              OR error_message LIKE '%%reference target(s) not found%%'
              OR error_message LIKE '%%Dependency belum siap%%'
              OR error_message LIKE '%%dependency belum siap%%'
              OR error_message LIKE '%%Dibutuhkan oleh resource lain sebagai dependency%%'
          )
        """,
        (SYNC_STATUS_WAITING, MAX_ATTEMPTS),
    )
    frappe.db.commit()


def recover_duplicate_failures():
    # Duplicate tanpa ID hasil lookup adalah error data/preflight, bukan dependency
    # sementara. Jangan reset attempts ke 0, supaya bisa mencapai failed_permanent.
    return


def _reference_values(value):
    references = []
    if isinstance(value, dict):
        reference = value.get("reference")
        if isinstance(reference, str):
            references.append(reference)
        for child in value.values():
            references.extend(_reference_values(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_reference_values(child))
    return references


def _dependency_rows_for_doc(doc):
    fhir = _as_dict(doc.fhir_payload)
    rows = []
    seen = set()

    for reference in _reference_values(fhir):
        if not isinstance(reference, str) or "/" not in reference:
            continue

        resource_type, local_id = reference.split("/", 1)
        if resource_type not in REFERENCE_RESOURCE_TYPES:
            continue

        row = (
            _find_dependency_queue(resource_type, local_id)
            or _find_dependency_queue_from_context(resource_type, fhir)
        )
        if row and row.get("name") and row.get("name") != doc.name and row.get("name") not in seen:
            seen.add(row.get("name"))
            rows.append(row)

    return rows


def _expand_with_dependencies(queue_names, max_rounds=5):
    expanded = list(dict.fromkeys(queue_names or []))

    for _round in range(int(max_rounds or 5)):
        changed = False
        for queue_name in list(expanded):
            if not frappe.db.exists(QUEUE_DOCTYPE, queue_name):
                continue
            doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
            for row in _dependency_rows_for_doc(doc):
                if row.get("name") not in expanded:
                    expanded.append(row.get("name"))
                    changed = True
        if not changed:
            break

    return expanded

def _prepare_pending_batch_dependencies(queue_names):
    if not queue_names:
        return

    for queue_name in queue_names:
        if not frappe.db.exists(QUEUE_DOCTYPE, queue_name):
            continue

        doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
        if getattr(doc, "import_status", None) in (IMPORT_STATUS_PENDING, IMPORT_STATUS_FAILED):
            try:
                process_import_queue_item(doc.name)
            except Exception:
                frappe.log_error(
                    title=f"Khanza SatuSehat Dependency Import Error: {doc.name}",
                    message=frappe.get_traceback(),
                )
                continue

        doc.reload()
        _queue_target_docstatus(doc)

    frappe.db.commit()

def process_queue(limit=50):
    limit = int(limit or 50)
    items = frappe.get_all(
        QUEUE_DOCTYPE,
        filters={
            "import_status": ["in", [IMPORT_STATUS_PENDING, IMPORT_STATUS_FAILED]],
        },
        fields=["name", "attempts", "last_attempt_at"],
        order_by="creation asc",
        limit_page_length=limit,
    )

    for item in items:
        if not _should_retry(item.last_attempt_at, item.attempts or 0):
            continue

        try:
            process_import_queue_item(item.name)
        except Exception:
            frappe.log_error(
                title=f"Khanza SatuSehat Sync Record Error: {item.name}",
                message=frappe.get_traceback(),
            )


def process_import_queue_item(queue_name):
    doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)

    if getattr(doc, "import_status", IMPORT_STATUS_IMPORTED) not in (
        IMPORT_STATUS_PENDING,
        IMPORT_STATUS_FAILED,
    ):
        return

    attempt_number = (doc.attempts or 0) + 1

    frappe.db.set_value(
        QUEUE_DOCTYPE,
        doc.name,
        {
            "import_status": IMPORT_STATUS_PROCESSING,
            "last_attempt_at": _now(),
            "attempts": attempt_number,
        },
        update_modified=True,
    )
    frappe.db.commit()

    log_name = _append_log(doc.name, attempt_number, "attempt")

    try:
        source = _as_dict(
            getattr(doc, "source_payload", None)
            or getattr(doc, "fhir_payload", None)
        )
        if not (source.get("resourceType") or source.get("resource_type")):
            raise frappe.ValidationError(_("Khanza payload requires resourceType or resource_type"))

        target_doc = import_khanza_to_healthcare_doc(doc, source, doc.external_id)
        target_docstatus = target_docstatus_label(getattr(target_doc, "docstatus", 0))
        validation_status, validation_summary = _technical_review_validation(doc, source, target_doc)

        updates = _filter_queue_updates(
            {
                "import_status": IMPORT_STATUS_IMPORTED,
                "imported_at": _now(),
                "target_doctype": target_doc.doctype,
                "target_docname": target_doc.name,
                "target_docstatus": target_docstatus,
                "review_status": getattr(doc, "review_status", None) or REVIEW_STATUS_PENDING,
                "revision_no": getattr(doc, "revision_no", None) or 1,
                "validation_status": validation_status,
                "validation_summary": validation_summary,
                "last_review_event_at": _now(),
                "attempts": 0,
                "last_attempt_at": None,
                "error_message": None,
            }
        )
        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            updates,
            update_modified=True,
        )

        frappe.db.set_value(
            LOG_DOCTYPE,
            log_name,
            {
                "status": "success",
                "response": _json_dumps(
                    {
                        "phase": "import",
                        "message": "Khanza payload imported into ERPNext Healthcare document",
                        "resource_type": source.get("resourceType") or source.get("resource_type"),
                        "queue_name": doc.name,
                        "target_doctype": target_doc.doctype,
                        "target_docname": target_doc.name,
                    }
                ),
            },
        )
        frappe.db.commit()
        doc.reload()
        _safe_append_review_parquet(
            doc,
            "imported",
            target_doc=target_doc,
            extra={
                "validation_status": validation_status,
                "validation_summary": validation_summary,
            },
        )

    except Exception as error:
        new_status = (
            IMPORT_STATUS_FAILED_PERMANENT
            if attempt_number >= MAX_ATTEMPTS
            else IMPORT_STATUS_FAILED
        )

        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            {
                "import_status": new_status,
                "error_message": str(error),
            },
            update_modified=True,
        )

        frappe.db.set_value(
            LOG_DOCTYPE,
            log_name,
            {
                "status": "failure",
                "error": str(error),
            },
        )
        frappe.db.commit()
        doc.reload()
        _safe_append_review_parquet(
            doc,
            "import_failed",
            extra={"error": str(error), "attempt_number": attempt_number},
        )
        raise


def _send_queue_names_in_order(
    queue_names,
    respect_retry_delay=False,
    max_rounds=5,
    max_attempts_per_call=None,
    max_seconds_per_call=None,
):
    pending_names = _expand_with_dependencies(queue_names)
    _prepare_pending_batch_dependencies(pending_names)
    pending_names = _expand_with_dependencies(pending_names)
    started_at = time.monotonic()
    stats = {
        "requested": len(list(dict.fromkeys(queue_names or []))),
        "expanded": len(pending_names),
        "attempted": 0,
        "sent": 0,
        "released_waiting": 0,
        "waiting_dependency": 0,
        "waiting_submission": 0,
        "skipped": 0,
        "failed": 0,
        "rounds": 0,
        "stalled": False,
        "stop_reason": None,
        "remaining_pending": [],
    }

    for _round in range(int(max_rounds or 5)):
        if not pending_names:
            break

        stats["rounds"] += 1
        docs = [
            frappe.get_doc(QUEUE_DOCTYPE, name)
            for name in pending_names
            if frappe.db.exists(QUEUE_DOCTYPE, name)
        ]
        docs.sort(key=_resource_sort_key)

        next_pending = []
        progressed = False

        for index, doc in enumerate(docs):
            if max_attempts_per_call and stats["attempted"] >= int(max_attempts_per_call):
                next_pending.extend([remaining_doc.name for remaining_doc in docs[index:]])
                stats["stop_reason"] = "batch_limit"
                break

            if max_seconds_per_call and (time.monotonic() - started_at) >= int(max_seconds_per_call):
                next_pending.extend([remaining_doc.name for remaining_doc in docs[index:]])
                stats["stop_reason"] = "time_budget"
                break

            if respect_retry_delay and not _should_retry(doc.last_attempt_at, doc.attempts or 0):
                next_pending.append(doc.name)
                continue

            try:
                stats["attempted"] += 1
                result = send_queue_item(doc.name)
                released_waiting = []
                if isinstance(result, dict):
                    released_waiting = result.get("released_waiting") or []
                    result = result.get("status")

                if result == "waiting_dependency":
                    stats["waiting_dependency"] += 1
                    next_pending.extend(
                        name for name in _expand_with_dependencies([doc.name]) if name != doc.name
                    )
                elif result == "waiting_submission":
                    stats["waiting_submission"] += 1
                    next_pending.append(doc.name)
                elif result == "sent":
                    stats["sent"] += 1
                    if released_waiting:
                        stats["released_waiting"] += len(released_waiting)
                        next_pending.extend(released_waiting)
                    progressed = True
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["failed"] += 1
                frappe.log_error(
                    title=f"Khanza SatuSehat Send Error: {doc.name}",
                    message=frappe.get_traceback(),
                )

        next_pending = list(dict.fromkeys(next_pending))
        if not next_pending:
            break

        pending_names = _expand_with_dependencies(next_pending)
        if stats["stop_reason"]:
            break

        if not progressed:
            stats["stalled"] = True
            stats["stop_reason"] = "waiting_dependency_or_no_progress"
            break

    stats["remaining_pending"] = pending_names
    return stats


def send_approved_queue(limit=50):
    recover_stuck_processing(minutes=30)
    recover_dependency_failures()
    recover_duplicate_failures()
    release_waiting_dependencies()

    limit = int(limit or 50)

    items = frappe.get_all(
        QUEUE_DOCTYPE,
        filters={
            "import_status": IMPORT_STATUS_IMPORTED,
            "approval_status": "Approved",
            "target_docstatus": "Submitted",
            "sync_status": ["in", ["pending", "failed"]],
        },
        fields=["name", "resource_type", "creation", "attempts", "last_attempt_at"],
        limit_page_length=limit,
    )

    items.sort(key=lambda row: (
        RESOURCE_SEND_ORDER.get(row.resource_type, 999),
        row.creation,
        row.name,
    ))

    return _send_queue_names_in_order(
        [item.name for item in items],
        respect_retry_delay=True,
        max_rounds=5,
        max_attempts_per_call=limit,
        max_seconds_per_call=None,
    )


def send_many(
    queue_names,
    max_attempts_per_call=SEND_BATCH_LIMIT,
    max_seconds_per_call=SEND_TIME_BUDGET_SECONDS,
):
    recover_stuck_processing(minutes=30)
    recover_dependency_failures()
    recover_duplicate_failures()
    release_waiting_dependencies()

    names = _expand_with_dependencies(_parse_names(queue_names))
    return _send_queue_names_in_order(
        names,
        respect_retry_delay=False,
        max_rounds=5,
        max_attempts_per_call=max_attempts_per_call,
        max_seconds_per_call=max_seconds_per_call,
    )


def process_queue_item(queue_name):
    return send_queue_item(queue_name)


def _is_stale_processing(doc, minutes=30):
    if doc.sync_status != "processing":
        return False

    if not doc.last_attempt_at:
        return True

    return frappe.utils.time_diff_in_seconds(_now(), doc.last_attempt_at) >= (int(minutes) * 60)


def send_queue_item(queue_name):
    doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)

    if getattr(doc, "import_status", IMPORT_STATUS_IMPORTED) != IMPORT_STATUS_IMPORTED:
        return "skipped"

    if doc.approval_status != "Approved":
        return "skipped"

    if not _is_queue_target_submitted(doc):
        _mark_waiting_submission(doc)
        return "waiting_submission"

    if doc.sync_status == "processing" and not _is_stale_processing(doc, minutes=30):
        return "skipped"

    if doc.sync_status not in ("pending", "failed", "processing"):
        return "skipped"

    preflight_fhir = None
    try:
        preflight_fhir = _normalize_fhir_for_satusehat(_as_dict(doc.fhir_payload))
        if not preflight_fhir.get("resourceType"):
            raise frappe.ValidationError(_("FHIR payload with resourceType is required"))
        preflight_fhir = _resolve_fhir_references(preflight_fhir)
    except DependencyNotReady as error:
        _mark_waiting_dependency(doc, str(error))
        return "waiting_dependency"
    except Exception:
        preflight_fhir = None

    sent_to_satusehat = False
    satusehat_success = {}

    attempt_number = (doc.attempts or 0) + 1

    frappe.db.set_value(
        QUEUE_DOCTYPE,
        doc.name,
        {
            "sync_status": "processing",
            "last_attempt_at": _now(),
            "attempts": attempt_number,
        },
        update_modified=True,
    )
    frappe.db.commit()

    log_name = _append_log(doc.name, attempt_number, "attempt")

    try:
        fhir = preflight_fhir
        if fhir is None:
            fhir = _as_dict(doc.fhir_payload)
            if not fhir.get("resourceType"):
                raise frappe.ValidationError(_("FHIR payload with resourceType is required"))

            fhir = _normalize_fhir_for_satusehat(fhir)
            fhir = _resolve_fhir_references(fhir)

        # satusehat_resource_id adalah satu-satunya ID asli SATUSEHAT.
        # ID lokal dari Khanza tidak boleh dipakai sebagai target PUT create,
        # karena SATUSEHAT akan menolak jika resource tersebut belum ada.
        resource_id = getattr(doc, "satusehat_resource_id", None)
        effective_method = "POST"

        if resource_id and not _satusehat_resource_exists(doc.resource_type, resource_id):
            frappe.db.set_value(
                QUEUE_DOCTYPE,
                doc.name,
                {
                    "satusehat_resource_id": None,
                    "error_message": (
                        f"ID SATUSEHAT lama {doc.resource_type}/{resource_id} tidak ditemukan; "
                        "resource akan dibuat ulang."
                    ),
                },
                update_modified=True,
            )
            frappe.db.commit()
            resource_id = None

        if resource_id:
            fhir["id"] = resource_id
            effective_method = "PUT"
            url = _resource_url(doc.resource_type, resource_id)
        else:
            # Untuk create baru, jangan kirim id lokal ke SATUSEHAT.
            # SATUSEHAT yang akan generate id resource asli.
            fhir.pop("id", None)

            existing = _find_existing_satusehat_resource(doc.resource_type, fhir)
            if existing:
                resource_id = existing.get("id")
                fhir["id"] = resource_id
                _safe_store_satusehat_resource_id(doc, fhir, resource_id)
                effective_method = "PUT"
                url = _resource_url(doc.resource_type, resource_id)
            else:
                url = _endpoint_for(doc, fhir)

        response = requests.request(
            effective_method,
            url,
            headers=_satusehat_headers(),
            data=_json_dumps(fhir).encode("utf-8"),
            timeout=SATUSEHAT_HTTP_TIMEOUT_SECONDS,
        )

        response_text = response.text or ""

        if not response.ok:
            if effective_method == "POST" and _is_duplicate_response(response_text):
                existing = _find_existing_satusehat_resource(doc.resource_type, fhir)
                if existing:
                    resource_id = existing.get("id")
                    fhir["id"] = resource_id
                    _safe_store_satusehat_resource_id(doc, fhir, resource_id)

                    url = _resource_url(doc.resource_type, resource_id)
                    response = requests.request(
                        "PUT",
                        url,
                        headers=_satusehat_headers(),
                        data=_json_dumps(fhir).encode("utf-8"),
                        timeout=SATUSEHAT_HTTP_TIMEOUT_SECONDS,
                    )

                    response_text = response.text or ""
                    effective_method = "PUT"
                else:
                    resource_id = _find_sent_resource_id_by_code(doc.resource_type, fhir)
                    if resource_id:
                        fhir["id"] = resource_id
                        _safe_store_satusehat_resource_id(doc, fhir, resource_id)
                        response = None
                        response_text = _json_dumps(
                            {
                                "resourceType": doc.resource_type,
                                "id": resource_id,
                                "duplicateResolvedFromLocalQueue": True,
                            }
                        )
                        effective_method = "SKIP_DUPLICATE"

            if response is not None and not response.ok:
                if effective_method == "POST" and _is_duplicate_response(response_text):
                    raise frappe.ValidationError(
                        "Duplicate resource already exists in SatuSehat, "
                        f"but lookup did not return an id: {response_text}"
                    )
                elif _is_reference_not_found_response(response_text):
                    _reset_missing_reference_targets(fhir, response_text)
                    frappe.db.commit()
                    raise DependencyNotReady(f"SATUSEHAT dependency belum siap: {response_text}")
                else:
                    raise frappe.ValidationError(f"HTTP {response.status_code}: {response_text}")

        if not sent_to_satusehat:
            sent_to_satusehat = True
            satusehat_success = {
                "status_code": response.status_code if response is not None else 200,
                "method": effective_method,
                "url": url,
                "body": response_text,
            }

        response_resource_id = _response_resource_id(response_text) or resource_id
        if response_resource_id:
            _safe_store_satusehat_resource_id(doc, fhir, response_resource_id)

        updates = _filter_queue_updates(
            {
                "sync_status": "sent",
                "sent_at": _now(),
                "last_review_event_at": _now(),
                "error_message": None,
            }
        )
        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            updates,
            update_modified=True,
        )

        frappe.db.set_value(
            LOG_DOCTYPE,
            log_name,
            {
                "status": "success",
                "response": _json_dumps(
                    {
                        "status_code": response.status_code if response is not None else 200,
                        "method": effective_method,
                        "url": url,
                        "body": response_text,
                    }
                ),
            },
        )
        frappe.db.commit()
        doc.reload()
        released_waiting = release_waiting_dependencies()
        return {
            "status": "sent",
            "released_waiting": released_waiting,
        }

    except DependencyNotReady as error:
        updates = _filter_queue_updates(
            {
                "sync_status": SYNC_STATUS_WAITING,
                "last_attempt_at": None,
                "last_review_event_at": _now(),
                "error_message": str(error),
            }
        )
        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            updates,
            update_modified=True,
        )

        frappe.db.set_value(
            LOG_DOCTYPE,
            log_name,
            {
                "status": "failure",
                "error": str(error),
            },
        )

        frappe.db.commit()
        doc.reload()
        _safe_append_review_parquet(
            doc,
            "waiting_dependency",
            target_doc=_target_doc_for_queue(doc),
            extra={"error": str(error), "attempt_number": attempt_number},
        )
        return "waiting_dependency"
    except Exception as error:
        if sent_to_satusehat:
            warning = f"SatuSehat success, ERPNext post-processing failed: {error}"

            updates = _filter_queue_updates(
                {
                    "sync_status": "sent",
                    "sent_at": _now(),
                    "last_review_event_at": _now(),
                    "error_message": warning,
                }
            )
            frappe.db.set_value(
                QUEUE_DOCTYPE,
                doc.name,
                updates,
                update_modified=True,
            )

            frappe.db.set_value(
                LOG_DOCTYPE,
                log_name,
                {
                    "status": "success",
                    "response": _json_dumps(
                        {
                            **satusehat_success,
                            "post_processing_warning": str(error),
                        }
                    ),
                },
            )

            frappe.db.commit()
            doc.reload()

            frappe.log_error(
                title=f"Khanza SatuSehat Post-Success Error: {doc.name}",
                message=frappe.get_traceback(),
            )
            released_waiting = release_waiting_dependencies()
            return {
                "status": "sent",
                "released_waiting": released_waiting,
            }

        new_status = "failed_permanent" if attempt_number >= MAX_ATTEMPTS else "failed"

        updates = _filter_queue_updates(
            {
                "sync_status": new_status,
                "last_review_event_at": _now(),
                "error_message": str(error),
            }
        )
        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            updates,
            update_modified=True,
        )

        frappe.db.set_value(
            LOG_DOCTYPE,
            log_name,
            {
                "status": "failure",
                "error": str(error),
            },
        )

        frappe.db.commit()
        doc.reload()
        _safe_append_review_parquet(
            doc,
            "send_failed",
            target_doc=_target_doc_for_queue(doc),
            extra={
                "error": str(error),
                "attempt_number": attempt_number,
                "sync_status": new_status,
            },
        )
        raise

