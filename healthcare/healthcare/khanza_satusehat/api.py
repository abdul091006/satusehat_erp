import frappe
from frappe import _

from .constants import (
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_FAILED_PERMANENT,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_PENDING,
    LOG_DOCTYPE,
    QUEUE_DOCTYPE,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_NEEDS_CORRECTION,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_REJECTED,
    VALIDATION_STATUS_UNCHECKED,
)
from .document_events import target_docstatus_label
from .logs import _safe_append_review_parquet
from .utils import (
    _as_dict,
    _canonical_source_json,
    _extract_external_id,
    _extract_source_payload,
    _get_queue_name,
    _get_request_payload,
    _json_dumps,
    _normalize_method,
    _now,
    _parse_names,
    _queue_response,
)
from .workers import process_import_queue_item, release_waiting_dependencies

def _queue_meta_has(fieldname):
	return frappe.get_meta(QUEUE_DOCTYPE).has_field(fieldname)

def _filter_queue_updates(values):
	return {
		fieldname: value
		for fieldname, value in values.items()
		if _queue_meta_has(fieldname)
	}

def _ensure_imported(doc):
	import_status = getattr(doc, "import_status", IMPORT_STATUS_IMPORTED)
	if import_status in (IMPORT_STATUS_PENDING, IMPORT_STATUS_FAILED):
		try:
			process_import_queue_item(doc.name)
		except Exception:
			frappe.log_error(
				title=f"Khanza SatuSehat Import Before Approval Error: {doc.name}",
				message=frappe.get_traceback(),
			)
		doc.reload()
	return getattr(doc, "import_status", IMPORT_STATUS_IMPORTED) == IMPORT_STATUS_IMPORTED

def _target_docstatus_for_queue(doc):
	target_doctype = getattr(doc, "target_doctype", None)
	target_docname = getattr(doc, "target_docname", None)
	if not target_doctype or not target_docname:
		return "Draft"
	if not frappe.db.exists(target_doctype, target_docname):
		return "Draft"
	return target_docstatus_label(frappe.db.get_value(target_doctype, target_docname, "docstatus"))

def _refresh_target_docstatus(doc):
	status = _target_docstatus_for_queue(doc)
	if frappe.get_meta(QUEUE_DOCTYPE).has_field("target_docstatus"):
		frappe.db.set_value(
			QUEUE_DOCTYPE,
			doc.name,
			"target_docstatus",
			status,
			update_modified=False,
		)
		doc.target_docstatus = status
	return status

def _target_document_label(doc):
	target_doctype = getattr(doc, "target_doctype", None) or "target document"
	target_docname = getattr(doc, "target_docname", None) or "-"
	return f"{target_doctype}/{target_docname}"

def _get_target_document(doc):
	target_doctype = getattr(doc, "target_doctype", None)
	target_docname = getattr(doc, "target_docname", None)
	if target_doctype and target_docname and frappe.db.exists(target_doctype, target_docname):
		return frappe.get_doc(target_doctype, target_docname)
	return None

def _submit_target_document(doc):
	target_doc = _get_target_document(doc)
	if not target_doc:
		return None

	if int(getattr(target_doc, "docstatus", 0) or 0) == 1:
		return target_doc

	if int(getattr(target_doc, "docstatus", 0) or 0) == 2:
		frappe.throw(_("Target ERPNext document {0} is Cancelled").format(_target_document_label(doc)))

	target_doc.flags.ignore_permissions = True
	target_doc.submit()
	target_doc.reload()
	return target_doc

def _ensure_target_submitted(doc, auto_submit=False):
	status = _refresh_target_docstatus(doc)
	if status == "Submitted":
		return True

	if auto_submit and status == "Draft":
		_submit_target_document(doc)
		doc.reload()
		status = _refresh_target_docstatus(doc)
		if status == "Submitted":
			return True

	message = (
		f"Target ERPNext document {_target_document_label(doc)} masih {status}. "
		"Submit target document before SatuSehat approval."
	)
	if getattr(doc, "sync_status", None) != "sent":
		updates = _filter_queue_updates(
			{
				"approval_status": "Pending",
				"approved_by": None,
				"approved_at": None,
				"sync_status": "pending",
				"last_review_event_at": _now(),
				"error_message": message,
			}
		)
		frappe.db.set_value(QUEUE_DOCTYPE, doc.name, updates, update_modified=True)
		doc.approval_status = "Pending"
		doc.approved_by = None
		doc.approved_at = None
		doc.sync_status = "pending"
		doc.error_message = message
	return False

def _queue_status_summary(queue_names):
	queue_names = _parse_names(queue_names)
	if not queue_names:
		return {
			"requested": 0,
			"by_sync_status": {},
			"by_import_status": {},
			"by_review_status": {},
			"by_approval_status": {},
			"by_target_docstatus": {},
			"items": [],
		}

	rows = frappe.get_all(
		QUEUE_DOCTYPE,
		filters={"name": ["in", queue_names]},
		fields=[
			"name",
			"resource_type",
			"import_status",
			"review_status",
			"revision_no",
			"validation_status",
			"approval_status",
			"sync_status",
			"target_docstatus",
			"attempts",
			"error_message",
		],
		limit_page_length=len(queue_names),
	)

	summary = {
		"requested": len(queue_names),
		"by_sync_status": {},
		"by_import_status": {},
		"by_review_status": {},
		"by_approval_status": {},
		"by_target_docstatus": {},
		"items": rows,
	}
	for row in rows:
		for key, fieldname in (
			("by_sync_status", "sync_status"),
			("by_import_status", "import_status"),
			("by_review_status", "review_status"),
			("by_approval_status", "approval_status"),
			("by_target_docstatus", "target_docstatus"),
		):
			value = row.get(fieldname) or "unknown"
			summary[key][value] = summary[key].get(value, 0) + 1
	return summary

def _enqueue_send_many(queue_names):
	queue_names = _parse_names(queue_names)
	if not queue_names:
		return _queue_status_summary([])

	frappe.enqueue(
		"healthcare.healthcare.khanza_main.send_many",
		queue_names=queue_names,
		queue="long",
		enqueue_after_commit=True,
		job_name=f"khanza-satusehat-send-{frappe.generate_hash(length=10)}",
	)

	summary = _queue_status_summary(queue_names)
	summary["queued"] = True
	summary["queued_count"] = len(queue_names)
	return summary

def _enqueue_approved_queue(limit=200):
	limit = int(limit or 200)
	frappe.enqueue(
		"healthcare.healthcare.khanza_main.send_approved_queue",
		limit=limit,
		queue="long",
		enqueue_after_commit=True,
		job_name=f"khanza-satusehat-approved-send-{frappe.generate_hash(length=10)}",
	)
	return {"queued": True, "limit": limit}

@frappe.whitelist(allow_guest=True)
def receive_document(**kwargs):
	payload = _get_request_payload(kwargs)
	payload = _as_dict(payload)
	source = _extract_source_payload(payload)
	external_id = _extract_external_id(payload, source)
	resource_type = payload.get("resource_type") or source.get("resource_type") or source.get("resourceType")

	if not external_id:
		frappe.throw(_("external_id is required"))

	existing = frappe.db.exists(QUEUE_DOCTYPE, {"external_id": external_id})
	if existing:
		doc = frappe.get_doc(QUEUE_DOCTYPE, existing)
		current_source = getattr(doc, "source_payload", None) or getattr(doc, "fhir_payload", None)
		payload_changed = _canonical_source_json(current_source) != _canonical_source_json(source)
		already_sent = doc.sync_status == "sent"

		if payload_changed:
			doc.resource_type = resource_type
			doc.source_system = payload.get("source_system") or "khanza"
			doc.method = _normalize_method(payload.get("method") or payload.get("satusehat_method"))
			doc.endpoint_path = payload.get("endpoint_path") or payload.get("satusehat_path")
			doc.payload = _json_dumps(payload)
			doc.source_payload = _json_dumps(source)
			doc.fhir_payload = _json_dumps(source) if source.get("resourceType") else None
			doc.import_status = IMPORT_STATUS_PENDING
			doc.imported_at = None
			doc.attempts = 0
			doc.last_attempt_at = None
			if _queue_meta_has("review_status"):
				doc.review_status = REVIEW_STATUS_PENDING
			if _queue_meta_has("revision_no"):
				doc.revision_no = (doc.revision_no or 0) + 1
			if _queue_meta_has("validation_status"):
				doc.validation_status = VALIDATION_STATUS_UNCHECKED
			if _queue_meta_has("validation_summary"):
				doc.validation_summary = None
			if _queue_meta_has("last_review_event_at"):
				doc.last_review_event_at = _now()

			doc.approval_status = "Pending"
			doc.approved_by = None
			doc.approved_at = None
			doc.rejection_reason = None
			doc.sync_status = "pending"
			doc.sent_at = None
			doc.error_message = (
				"Updated from Khanza after SatuSehat sent; needs review before update"
				if already_sent
				else "Updated from Khanza, needs re-approval"
			)

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
		if already_sent and not payload_changed:
			return _queue_response(doc, "already_sent")
		return _queue_response(doc, "updated_for_review" if payload_changed else "already_queued")

	doc = frappe.get_doc(
		{
			"doctype": QUEUE_DOCTYPE,
			"external_id": external_id,
			"resource_type": resource_type,
			"source_system": payload.get("source_system") or "khanza",
			"method": _normalize_method(payload.get("method") or payload.get("satusehat_method")),
			"endpoint_path": payload.get("endpoint_path") or payload.get("satusehat_path"),
			"import_status": IMPORT_STATUS_PENDING,
			"approval_status": "Pending",
			"sync_status": "pending",
			"review_status": REVIEW_STATUS_PENDING,
			"revision_no": 1,
			"validation_status": VALIDATION_STATUS_UNCHECKED,
			"attempts": 0,
			"payload": _json_dumps(payload),
			"source_payload": _json_dumps(source),
			"fhir_payload": _json_dumps(source) if source.get("resourceType") else None,
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
			enqueue_after_commit=True,
		)
	doc.reload()

	return _queue_response(doc, "queued_for_import")

@frappe.whitelist(allow_guest=True)
def approve(queue_name):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
	if doc.sync_status == "sent":
		return _queue_response(doc, "already_sent")
	if not _ensure_imported(doc):
		frappe.throw(
			_("Sync record belum berhasil di-import ke ERPNext: {0}").format(
				doc.error_message or doc.import_status
			)
		)
	if not _ensure_target_submitted(doc, auto_submit=True):
		frappe.throw(_(doc.error_message))

	if _queue_meta_has("review_status"):
		doc.review_status = REVIEW_STATUS_APPROVED
	if _queue_meta_has("last_review_event_at"):
		doc.last_review_event_at = _now()
	doc.approval_status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_at = _now()
	doc.rejection_reason = None
	if doc.sync_status != "sent":
		doc.sync_status = "pending"
		doc.error_message = None
	doc.save(ignore_permissions=True)
	_safe_append_review_parquet(
		doc,
		"approved",
		target_doc=_get_target_document(doc),
		extra={"approved_by": frappe.session.user},
	)
	summary = _enqueue_send_many([doc.name])
	doc.reload()
	response = _queue_response(doc, "approved")
	response["send_summary"] = summary
	return response

@frappe.whitelist(allow_guest=True)
def approve_many(queue_names=None, names=None):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	queue_names = _parse_names(queue_names or names)
	if not queue_names:
		frappe.throw(_("No sync records selected"))

	approved = []
	skipped = []
	for queue_name in queue_names:
		doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
		if doc.sync_status == "sent":
			skipped.append({"queue_name": queue_name, "reason": "already_sent"})
			continue
		if not _ensure_imported(doc):
			skipped.append(
				{
					"queue_name": queue_name,
					"reason": "not_imported",
					"import_status": getattr(doc, "import_status", None),
					"error_message": getattr(doc, "error_message", None),
				}
			)
			continue
		try:
			target_ready = _ensure_target_submitted(doc, auto_submit=True)
		except Exception as error:
			skipped.append(
				{
					"queue_name": queue_name,
					"reason": "target_submit_failed",
					"target_docstatus": getattr(doc, "target_docstatus", None),
					"error_message": str(error),
				}
			)
			continue
		if not target_ready:
			skipped.append(
				{
					"queue_name": queue_name,
					"reason": "target_not_submitted",
					"target_docstatus": getattr(doc, "target_docstatus", None),
					"error_message": getattr(doc, "error_message", None),
				}
			)
			continue

		if _queue_meta_has("review_status"):
			doc.review_status = REVIEW_STATUS_APPROVED
		if _queue_meta_has("last_review_event_at"):
			doc.last_review_event_at = _now()
		doc.approval_status = "Approved"
		doc.approved_by = frappe.session.user
		doc.approved_at = _now()
		doc.rejection_reason = None
		if doc.sync_status != "sent":
			doc.sync_status = "pending"
			doc.error_message = None
		doc.save(ignore_permissions=True)
		_safe_append_review_parquet(
			doc,
			"approved",
			target_doc=_get_target_document(doc),
			extra={"approved_by": frappe.session.user},
		)
		approved.append(doc.name)

	if approved:
		send_summary = _enqueue_send_many(approved)
	else:
		send_summary = _queue_status_summary([])

	return {
		"status": "ok",
		"message": "bulk_approval_queued",
		"approved_count": len(approved),
		"skipped_count": len(skipped),
		"approved": approved,
		"skipped": skipped,
		"send_summary": send_summary,
	}

def _is_truthy(value):
	return str(value).lower() in ("1", "true", "yes", "y")

@frappe.whitelist(allow_guest=True)
def reject(queue_name, reason, final=False):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
	if doc.sync_status == "sent":
		frappe.throw(_("Sent sync record cannot be rejected"))

	final = _is_truthy(final)
	if _queue_meta_has("review_status"):
		doc.review_status = REVIEW_STATUS_REJECTED if final else REVIEW_STATUS_NEEDS_CORRECTION
	if _queue_meta_has("last_review_event_at"):
		doc.last_review_event_at = _now()
	doc.approval_status = "Rejected" if final else "Pending"
	doc.approved_by = None
	doc.approved_at = None
	doc.rejection_reason = reason
	if doc.sync_status != "sent":
		doc.sync_status = "pending"
		doc.error_message = reason or ("Rejected" if final else "Needs correction")
	doc.save(ignore_permissions=True)
	_safe_append_review_parquet(
		doc,
		"rejected" if final else "needs_correction",
		target_doc=_get_target_document(doc),
		extra={"reason": reason, "final": final},
	)
	return _queue_response(doc, "rejected" if final else "needs_correction")

@frappe.whitelist(allow_guest=True)
def needs_correction(queue_name, reason):
	return reject(queue_name=queue_name, reason=reason, final=False)

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
			enqueue_after_commit=True,
		)
		doc.import_status = IMPORT_STATUS_PENDING
		doc.error_message = None
		return _queue_response(doc, "import_retry_initiated")

	if doc.approval_status != "Approved":
		frappe.throw(_("Only approved sync records can be retried for SatuSehat sending"))
	if not _ensure_target_submitted(doc):
		frappe.throw(_(doc.error_message))

	frappe.db.set_value(
		QUEUE_DOCTYPE,
		doc.name,
		{
			"sync_status": "pending",
			"error_message": None,
		},
		update_modified=True,
	)
	summary = _enqueue_send_many([doc.name])
	doc.reload()
	response = _queue_response(doc, "retry_initiated")
	response["send_summary"] = summary
	return response

@frappe.whitelist(allow_guest=True)
def process_approved(limit=200):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	limit = int(limit or 200)
	release_waiting_dependencies()
	items = frappe.get_all(
		QUEUE_DOCTYPE,
		filters={
			"import_status": IMPORT_STATUS_IMPORTED,
			"approval_status": "Approved",
			"sync_status": ["in", ["pending", "failed"]],
		},
		fields=["name"],
		limit_page_length=limit,
	)
	queue_names = []
	skipped = []
	for item in items:
		doc = frappe.get_doc(QUEUE_DOCTYPE, item.name)
		if _ensure_target_submitted(doc):
			queue_names.append(doc.name)
		else:
			skipped.append(
				{
					"queue_name": doc.name,
					"reason": "target_not_submitted",
					"target_docstatus": getattr(doc, "target_docstatus", None),
					"error_message": getattr(doc, "error_message", None),
				}
			)
	summary = _enqueue_send_many(queue_names)
	return {
		"status": "ok",
		"message": "approved_pending_queued",
		"count": len(queue_names),
		"skipped_count": len(skipped),
		"queue_names": queue_names,
		"skipped": skipped,
		"send_summary": summary,
	}

@frappe.whitelist()
def backfill_source_fields(limit=500):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	from .healthcare_import import backfill_khanza_source_fields

	return backfill_khanza_source_fields(limit=limit)

@frappe.whitelist(allow_guest=True)
def approve_pending_and_process(limit=200):
	frappe.only_for(("System Manager", "Healthcare Administrator"))
	limit = int(limit or 200)
	release_waiting_dependencies()
	items = frappe.get_all(
		QUEUE_DOCTYPE,
		filters={
			"import_status": ["in", [IMPORT_STATUS_PENDING, IMPORT_STATUS_FAILED, IMPORT_STATUS_IMPORTED]],
			"approval_status": ["in", ["Pending", "Approved"]],
			"sync_status": ["in", ["pending", "failed"]],
		},
		fields=["name"],
		order_by="creation asc",
		limit_page_length=limit,
	)
	queue_names = []
	skipped = []
	for item in items:
		doc = frappe.get_doc(QUEUE_DOCTYPE, item.name)
		if not _ensure_imported(doc):
			skipped.append(
				{
					"queue_name": doc.name,
					"reason": "not_imported",
					"import_status": getattr(doc, "import_status", None),
					"error_message": getattr(doc, "error_message", None),
				}
			)
			continue
		try:
			target_ready = _ensure_target_submitted(doc, auto_submit=True)
		except Exception as error:
			skipped.append(
				{
					"queue_name": doc.name,
					"reason": "target_submit_failed",
					"target_docstatus": getattr(doc, "target_docstatus", None),
					"error_message": str(error),
				}
			)
			continue
		if not target_ready:
			skipped.append(
				{
					"queue_name": doc.name,
					"reason": "target_not_submitted",
					"target_docstatus": getattr(doc, "target_docstatus", None),
					"error_message": getattr(doc, "error_message", None),
				}
			)
			continue
		updates = _filter_queue_updates(
			{
				"approval_status": "Approved",
				"review_status": REVIEW_STATUS_APPROVED,
				"approved_by": frappe.session.user,
				"approved_at": _now(),
				"rejection_reason": None,
				"sync_status": "pending",
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
		doc.reload()
		_safe_append_review_parquet(
			doc,
			"approved",
			target_doc=_get_target_document(doc),
			extra={"approved_by": frappe.session.user},
		)
		queue_names.append(doc.name)

	summary = _enqueue_send_many(queue_names)
	return {
		"status": "ok",
		"message": "pending_approved_and_queued",
		"count": len(queue_names),
		"skipped_count": len(skipped),
		"queue_names": queue_names,
		"skipped": skipped,
		"send_summary": summary,
	}

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
			"review_status": getattr(doc, "review_status", None),
			"revision_no": getattr(doc, "revision_no", None),
			"validation_status": getattr(doc, "validation_status", None),
			"validation_summary": getattr(doc, "validation_summary", None),
			"approval_status": doc.approval_status,
			"sync_status": doc.sync_status,
			"attempts": doc.attempts,
			"last_attempt_at": doc.last_attempt_at,
			"error_message": doc.error_message,
			"target_doctype": getattr(doc, "target_doctype", None),
			"target_docname": getattr(doc, "target_docname", None),
			"target_docstatus": getattr(doc, "target_docstatus", None),
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

