import frappe

from .constants import (
	QUEUE_DOCTYPE,
	REVIEW_STATUS_NEEDS_CORRECTION,
	REVIEW_STATUS_PENDING,
	VALIDATION_STATUS_UNCHECKED,
)
from .logs import _safe_append_review_parquet
from .utils import _now


def _queue_meta_has(fieldname):
	return frappe.get_meta(QUEUE_DOCTYPE).has_field(fieldname)


def _filter_queue_updates(values):
	return {
		fieldname: value
		for fieldname, value in values.items()
		if _queue_meta_has(fieldname)
	}


def target_docstatus_label(docstatus):
	try:
		docstatus = int(docstatus or 0)
	except Exception:
		docstatus = 0

	if docstatus == 1:
		return "Submitted"
	if docstatus == 2:
		return "Cancelled"
	return "Draft"


def sync_queue_target_docstatus(doc, method=None):
	queue_name = getattr(doc, "khanza_queue", None)
	if not queue_name or not frappe.db.exists(QUEUE_DOCTYPE, queue_name):
		return

	from_import = bool(getattr(getattr(doc, "flags", None), "from_khanza_import", False))
	status = target_docstatus_label(getattr(doc, "docstatus", 0))
	updates = {"target_docstatus": status}

	queue_status = frappe.db.get_value(
		QUEUE_DOCTYPE,
		queue_name,
		[
			"sync_status",
			"approval_status",
			"review_status",
			"revision_no",
			"error_message",
		],
		as_dict=True,
	)

	if status == "Submitted":
		error_message = (queue_status or {}).get("error_message") or ""
		if "Submit target document" in error_message:
			updates["error_message"] = None
		if queue_status and not from_import and queue_status.get("sync_status") != "sent":
			updates.update(
				_filter_queue_updates(
					{
						"review_status": REVIEW_STATUS_PENDING,
						"approval_status": "Pending",
						"approved_by": None,
						"approved_at": None,
						"sync_status": "pending",
						"revision_no": (queue_status.get("revision_no") or 0) + 1,
						"validation_status": VALIDATION_STATUS_UNCHECKED,
						"validation_summary": None,
						"last_review_event_at": _now(),
						"error_message": None,
					}
				)
			)
	else:
		if queue_status and not from_import and queue_status.get("sync_status") != "sent":
			review_status = (
				REVIEW_STATUS_NEEDS_CORRECTION if status == "Cancelled" else REVIEW_STATUS_PENDING
			)
			updates.update(
				_filter_queue_updates(
					{
						"review_status": review_status,
						"approval_status": "Pending",
						"approved_by": None,
						"approved_at": None,
						"sync_status": "pending",
						"revision_no": (queue_status.get("revision_no") or 0) + 1,
						"validation_status": VALIDATION_STATUS_UNCHECKED,
						"validation_summary": None,
						"last_review_event_at": _now(),
						"error_message": None,
					}
				)
			)

	frappe.db.set_value(QUEUE_DOCTYPE, queue_name, _filter_queue_updates(updates), update_modified=True)

	if not from_import:
		queue_doc = frappe.get_doc(QUEUE_DOCTYPE, queue_name)
		event_type = {
			"Draft": "edited",
			"Submitted": "submitted",
			"Cancelled": "cancelled",
		}.get(status, "target_updated")
		_safe_append_review_parquet(
			queue_doc,
			event_type,
			target_doc=doc,
			extra={"method": method, "target_docstatus": status},
		)


def sync_all_queue_target_docstatus():
	if not frappe.db.exists("DocType", QUEUE_DOCTYPE):
		return

	if not frappe.get_meta(QUEUE_DOCTYPE).has_field("target_docstatus"):
		return

	rows = frappe.get_all(
		QUEUE_DOCTYPE,
		filters={
			"target_doctype": ["is", "set"],
			"target_docname": ["is", "set"],
		},
		fields=["name", "target_doctype", "target_docname"],
		limit_page_length=0,
	)

	for row in rows:
		status = "Draft"
		if frappe.db.exists(row.target_doctype, row.target_docname):
			docstatus = frappe.db.get_value(row.target_doctype, row.target_docname, "docstatus")
			status = target_docstatus_label(docstatus)
		frappe.db.set_value(
			QUEUE_DOCTYPE,
			row.name,
			"target_docstatus",
			status,
			update_modified=False,
		)

	frappe.db.commit()
