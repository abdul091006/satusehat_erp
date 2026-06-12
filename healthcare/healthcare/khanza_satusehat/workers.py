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
)
from .healthcare_import import import_fhir_to_healthcare_doc
from .logs import _append_log, _safe_append_success_ndjson
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


def recover_stuck_processing(minutes=30):
    """
    Recovery untuk queue yang nyangkut di status processing.

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
                title=f"Khanza SatuSehat Queue Error: {item.name}",
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
        fhir = _as_dict(doc.fhir_payload)
        if not fhir.get("resourceType"):
            raise frappe.ValidationError(_("FHIR payload with resourceType is required"))

        target_doc = import_fhir_to_healthcare_doc(doc, fhir, doc.external_id)

        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            {
                "import_status": IMPORT_STATUS_IMPORTED,
                "imported_at": _now(),
                "target_doctype": target_doc.doctype,
                "target_docname": target_doc.name,
                "attempts": 0,
                "last_attempt_at": None,
                "error_message": None,
            },
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
                        "message": "FHIR payload imported into ERPNext Healthcare document",
                        "resource_type": fhir.get("resourceType"),
                        "queue_name": doc.name,
                        "target_doctype": target_doc.doctype,
                        "target_docname": target_doc.name,
                    }
                ),
            },
        )
        frappe.db.commit()

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
        raise


def send_approved_queue(limit=50):
    recover_stuck_processing(minutes=30)

    limit = int(limit or 50)
    items = frappe.get_all(
        QUEUE_DOCTYPE,
        filters={
            "import_status": IMPORT_STATUS_IMPORTED,
            "approval_status": "Approved",
            "sync_status": ["in", ["pending", "failed"]],
        },
        fields=["name", "attempts", "last_attempt_at"],
        order_by="creation asc",
        limit_page_length=limit,
    )

    for item in items:
        if not _should_retry(item.last_attempt_at, item.attempts or 0):
            continue

        try:
            send_queue_item(item.name)
        except Exception:
            frappe.log_error(
                title=f"Khanza SatuSehat Send Error: {item.name}",
                message=frappe.get_traceback(),
            )


def send_many(queue_names):
    recover_stuck_processing(minutes=30)

    for queue_name in _parse_names(queue_names):
        try:
            send_queue_item(queue_name)
        except Exception:
            frappe.log_error(
                title=f"Khanza SatuSehat Bulk Send Error: {queue_name}",
                message=frappe.get_traceback(),
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
        return

    if doc.approval_status != "Approved":
        return

    if doc.sync_status == "processing" and not _is_stale_processing(doc, minutes=30):
        return

    if doc.sync_status not in ("pending", "failed", "processing"):
        return

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
        fhir = _as_dict(doc.fhir_payload)
        if not fhir.get("resourceType"):
            raise frappe.ValidationError(_("FHIR payload with resourceType is required"))

        fhir = _normalize_fhir_for_satusehat(fhir)

        resource_id = getattr(doc, "satusehat_resource_id", None) or fhir.get("id")
        effective_method = doc.method or "POST"

        if resource_id:
            fhir["id"] = resource_id
            effective_method = "PUT"
            url = _resource_url(doc.resource_type, resource_id)
        else:
            if effective_method == "POST":
                existing = _find_existing_satusehat_resource(doc.resource_type, fhir)
                if existing:
                    resource_id = existing.get("id")
                    fhir["id"] = resource_id
                    _safe_store_satusehat_resource_id(doc, fhir, resource_id)
                    effective_method = "PUT"
                    url = _resource_url(doc.resource_type, resource_id)
                else:
                    url = _endpoint_for(doc, fhir)
            else:
                url = _endpoint_for(doc, fhir)

        response = requests.request(
            effective_method,
            url,
            headers=_satusehat_headers(),
            data=_json_dumps(fhir).encode("utf-8"),
            timeout=30,
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
                        timeout=30,
                    )

                    response_text = response.text or ""
                    effective_method = "PUT"

            if not response.ok:
                raise frappe.ValidationError(f"HTTP {response.status_code}: {response_text}")

        sent_to_satusehat = True
        satusehat_success = {
            "status_code": response.status_code,
            "method": effective_method,
            "url": url,
            "body": response_text,
        }

        response_resource_id = _response_resource_id(response_text) or resource_id
        if response_resource_id:
            _safe_store_satusehat_resource_id(doc, fhir, response_resource_id)

        ndjson_path = _safe_append_success_ndjson(fhir, doc.name)

        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            {
                "sync_status": "sent",
                "sent_at": _now(),
                "error_message": None,
            },
            update_modified=True,
        )

        frappe.db.set_value(
            LOG_DOCTYPE,
            log_name,
            {
                "status": "success",
                "response": _json_dumps(
                    {
                        "status_code": response.status_code,
                        "method": effective_method,
                        "url": url,
                        "body": response_text,
                        "ndjson_path": ndjson_path,
                    }
                ),
            },
        )
        frappe.db.commit()

    except Exception as error:
        if sent_to_satusehat:
            warning = f"SatuSehat success, ERPNext post-processing failed: {error}"

            frappe.db.set_value(
                QUEUE_DOCTYPE,
                doc.name,
                {
                    "sync_status": "sent",
                    "sent_at": _now(),
                    "error_message": warning,
                },
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

            frappe.log_error(
                title=f"Khanza SatuSehat Post-Success Error: {doc.name}",
                message=frappe.get_traceback(),
            )
            return

        new_status = "failed_permanent" if attempt_number >= MAX_ATTEMPTS else "failed"

        frappe.db.set_value(
            QUEUE_DOCTYPE,
            doc.name,
            {
                "sync_status": new_status,
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
        raise