import frappe

from .constants import QUEUE_DOCTYPE
from .utils import _json_dumps


def _store_satusehat_resource_id(queue_doc, fhir, resource_id):
	if not resource_id:
		return

	fhir["id"] = resource_id
	queue_updates = {
		"fhir_payload": _json_dumps(fhir),
	}
	if frappe.get_meta(QUEUE_DOCTYPE).has_field("satusehat_resource_id"):
		queue_updates["satusehat_resource_id"] = resource_id

	frappe.db.set_value(
		QUEUE_DOCTYPE,
		queue_doc.name,
		queue_updates,
		update_modified=True,
	)

	target_doctype = getattr(queue_doc, "target_doctype", None)
	target_docname = getattr(queue_doc, "target_docname", None)
	if not target_doctype or not target_docname or not frappe.db.exists(target_doctype, target_docname):
		return

	target_meta = frappe.get_meta(target_doctype)
	target_updates = {}
	if target_meta.has_field("satusehat_resource_id"):
		target_updates["satusehat_resource_id"] = resource_id
	if target_meta.has_field("khanza_fhir_payload"):
		target_updates["khanza_fhir_payload"] = _json_dumps(fhir)

	if target_updates:
		frappe.db.set_value(
			target_doctype,
			target_docname,
			target_updates,
			update_modified=True,
		)

def _safe_store_satusehat_resource_id(queue_doc, fhir, resource_id):
	try:
		_store_satusehat_resource_id(queue_doc, fhir, resource_id)
	except Exception:
		frappe.log_error(
			title=f"Khanza SatuSehat Resource ID Store Error: {queue_doc.name}",
			message=frappe.get_traceback(),
		)
