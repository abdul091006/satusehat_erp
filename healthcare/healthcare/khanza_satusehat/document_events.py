import frappe

from .constants import QUEUE_DOCTYPE


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

	status = target_docstatus_label(getattr(doc, "docstatus", 0))
	updates = {"target_docstatus": status}

	queue_status = frappe.db.get_value(
		QUEUE_DOCTYPE,
		queue_name,
		["sync_status", "approval_status", "error_message"],
		as_dict=True,
	)

	if status == "Submitted":
		error_message = (queue_status or {}).get("error_message") or ""
		if "Submit target document" in error_message:
			updates["error_message"] = None
	else:
		if queue_status and queue_status.get("sync_status") != "sent":
			updates.update(
				{
					"approval_status": "Pending",
					"approved_by": None,
					"approved_at": None,
					"sync_status": "pending",
					"error_message": (
						f"Target ERPNext document {doc.doctype}/{doc.name} is {status}. "
						"Submit target document before SatuSehat approval."
					),
				}
			)

	frappe.db.set_value(QUEUE_DOCTYPE, queue_name, updates, update_modified=True)


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
