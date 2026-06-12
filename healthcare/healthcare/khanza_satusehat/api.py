import frappe
from frappe import _

from .constants import (
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_FAILED_PERMANENT,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_PENDING,
    LOG_DOCTYPE,
    QUEUE_DOCTYPE,
)
from .utils import (
    _as_dict,
    _canonical_fhir_json,
    _extract_external_id,
    _extract_fhir,
    _get_queue_name,
    _get_request_payload,
    _json_dumps,
    _normalize_method,
    _now,
    _parse_names,
    _queue_response,
)
from .workers import process_import_queue_item, send_many, send_queue_item

@frappe.whitelist(allow_guest=True)
def receive_document(**kwargs):
	payload = _get_request_payload(kwargs)
	payload = _as_dict(payload)
	fhir = _extract_fhir(payload)
	external_id = _extract_external_id(payload, fhir)

	if not external_id:
		frappe.throw(_("external_id is required"))

	existing = frappe.db.exists(QUEUE_DOCTYPE, {"external_id": external_id})
	if existing:
		doc = frappe.get_doc(QUEUE_DOCTYPE, existing)
		payload_changed = _canonical_fhir_json(doc.fhir_payload) != _canonical_fhir_json(fhir)

		if payload_changed:
			doc.resource_type = payload.get("resource_type") or fhir.get("resourceType")
			doc.source_system = payload.get("source_system") or "khanza"
			doc.method = _normalize_method(payload.get("method") or payload.get("satusehat_method"))
			doc.endpoint_path = payload.get("endpoint_path") or payload.get("satusehat_path")
			doc.payload = _json_dumps(payload)
			doc.fhir_payload = _json_dumps(fhir)
			doc.import_status = IMPORT_STATUS_PENDING
			doc.imported_at = None
			doc.approval_status = "Pending"
			doc.approved_by = None
			doc.approved_at = None
			doc.rejection_reason = None
			doc.sync_status = "pending"
			doc.attempts = 0
			doc.last_attempt_at = None
			doc.sent_at = None
			doc.error_message = "Updated from Khanza, needs re-approval"
			doc.save(ignore_permissions=True)

		if payload_changed or getattr(doc, "import_status", None) in (IMPORT_STATUS_PENDING, IMPORT_STATUS_FAILED):
			try:
				process_import_queue_item(doc.name)
			except Exception:
				frappe.log_error(
					title=f"Khanza SatuSehat Immediate Import Error: {doc.name}",
					message=frappe.get_traceback(),
				)
			doc.reload()
		return _queue_response(doc, "updated_for_review" if payload_changed else "already_queued")

	doc = frappe.get_doc(
		{
			"doctype": QUEUE_DOCTYPE,
			"external_id": external_id,
			"resource_type": payload.get("resource_type") or fhir.get("resourceType"),
			"source_system": payload.get("source_system") or "khanza",
			"method": _normalize_method(payload.get("method") or payload.get("satusehat_method")),
			"endpoint_path": payload.get("endpoint_path") or payload.get("satusehat_path"),
			"import_status": IMPORT_STATUS_PENDING,
			"approval_status": "Pending",
			"sync_status": "pending",
			"attempts": 0,
			"payload": _json_dumps(payload),
			"fhir_payload": _json_dumps(fhir),
		}
	)
	doc.insert(ignore_permissions=True)
	try:
		process_import_queue_item(doc.name)
	except Exception:
		frappe.log_error(
			title=f"Khanza SatuSehat Immediate Import Error: {doc.name}",
			message=frappe.get_traceback(),
		)
		frappe.enqueue(
			"healthcare.healthcare.khanza_main.process_import_queue_item",
			queue_name=doc.name,
			queue="long",
		)
	doc.reload()

	return _queue_response(doc, "queued_for_import")

@frappe.whitelist(allow_guest=True)
def approve(queue_name):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
	if doc.sync_status == "sent":
		return _queue_response(doc, "already_sent")
	if getattr(doc, "import_status", IMPORT_STATUS_IMPORTED) != IMPORT_STATUS_IMPORTED:
		frappe.throw(_("Only imported queue items can be approved for SatuSehat sending"))

	doc.approval_status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_at = _now()
	doc.rejection_reason = None
	if doc.sync_status == "failed_permanent":
		doc.sync_status = "pending"
	doc.save(ignore_permissions=True)
	frappe.enqueue(
		"healthcare.healthcare.khanza_main.send_queue_item",
		queue_name=doc.name,
		queue="long",
	)
	return _queue_response(doc, "approved")

@frappe.whitelist(allow_guest=True)
def approve_many(queue_names=None, names=None):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	queue_names = _parse_names(queue_names or names)
	if not queue_names:
		frappe.throw(_("No queue items selected"))

	approved = []
	skipped = []
	for queue_name in queue_names:
		doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
		if doc.sync_status == "sent":
			skipped.append({"queue_name": queue_name, "reason": "already_sent"})
			continue
		if getattr(doc, "import_status", IMPORT_STATUS_IMPORTED) != IMPORT_STATUS_IMPORTED:
			skipped.append({"queue_name": queue_name, "reason": "not_imported"})
			continue

		doc.approval_status = "Approved"
		doc.approved_by = frappe.session.user
		doc.approved_at = _now()
		doc.rejection_reason = None
		if doc.sync_status == "failed_permanent":
			doc.sync_status = "pending"
		doc.save(ignore_permissions=True)
		approved.append(doc.name)

	if approved:
		frappe.enqueue(
			"healthcare.healthcare.khanza_main.send_many",
			queue_names=approved,
			queue="long",
		)

	return {
		"status": "ok",
		"message": "bulk_approval_queued",
		"approved_count": len(approved),
		"skipped_count": len(skipped),
		"approved": approved,
		"skipped": skipped,
	}

@frappe.whitelist(allow_guest=True)
def reject(queue_name, reason):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
	if doc.sync_status == "sent":
		frappe.throw(_("Sent queue item cannot be rejected"))
	doc.approval_status = "Rejected"
	doc.rejection_reason = reason
	doc.save(ignore_permissions=True)
	return _queue_response(doc, "rejected")

@frappe.whitelist(allow_guest=True)
def retry(queue_name=None, external_id=None):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	queue_name = _get_queue_name(external_id=external_id, queue_name=queue_name)
	doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
	if doc.sync_status == "sent":
		return _queue_response(doc, "already_sent")

	if getattr(doc, "import_status", IMPORT_STATUS_IMPORTED) in (
		IMPORT_STATUS_FAILED,
		IMPORT_STATUS_FAILED_PERMANENT,
		IMPORT_STATUS_PENDING,
	):
		frappe.db.set_value(
			QUEUE_DOCTYPE,
			doc.name,
			{
				"import_status": IMPORT_STATUS_PENDING,
				"error_message": None,
			},
			update_modified=True,
		)
		frappe.enqueue(
			"healthcare.healthcare.khanza_main.process_import_queue_item",
			queue_name=doc.name,
			queue="long",
		)
		doc.import_status = IMPORT_STATUS_PENDING
		doc.error_message = None
		return _queue_response(doc, "import_retry_initiated")

	if doc.approval_status != "Approved":
		frappe.throw(_("Only approved queue items can be retried for SatuSehat sending"))

	frappe.db.set_value(
		QUEUE_DOCTYPE,
		doc.name,
		{
			"sync_status": "pending",
			"error_message": None,
		},
		update_modified=True,
	)
	frappe.enqueue(
		"healthcare.healthcare.khanza_main.send_queue_item",
		queue_name=doc.name,
		queue="long",
	)
	doc.sync_status = "pending"
	doc.error_message = None
	return _queue_response(doc, "retry_initiated")

@frappe.whitelist(allow_guest=True)
def status(external_id=None, queue_name=None):
	doc_name = _get_queue_name(external_id=external_id, queue_name=queue_name)
	doc = frappe.get_doc(QUEUE_DOCTYPE, doc_name)
	return {
		"status": "ok",
		"data": {
			"queue_name": doc.name,
			"external_id": doc.external_id,
			"resource_type": doc.resource_type,
			"satusehat_resource_id": getattr(doc, "satusehat_resource_id", None),
			"import_status": getattr(doc, "import_status", None),
			"approval_status": doc.approval_status,
			"sync_status": doc.sync_status,
			"attempts": doc.attempts,
			"last_attempt_at": doc.last_attempt_at,
			"error_message": doc.error_message,
			"target_doctype": getattr(doc, "target_doctype", None),
			"target_docname": getattr(doc, "target_docname", None),
			"sent_at": doc.sent_at,
		},
	}

@frappe.whitelist(allow_guest=True)
def failed(limit=100):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	limit = int(limit or 100)
	items = frappe.db.sql(
		f"""
		SELECT
			name,
			external_id,
			resource_type,
			import_status,
			approval_status,
			sync_status,
			attempts,
			error_message,
			creation,
			last_attempt_at
		FROM `tab{QUEUE_DOCTYPE}`
		WHERE import_status IN (%s, %s)
		   OR sync_status IN ('failed', 'failed_permanent')
		ORDER BY modified DESC
		LIMIT %s
		""",
		(IMPORT_STATUS_FAILED, IMPORT_STATUS_FAILED_PERMANENT, limit),
		as_dict=True,
	)
	return {"status": "ok", "count": len(items), "items": items}
