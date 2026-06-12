import frappe
from frappe.utils import now_datetime

from healthcare.healthcare.sync_all import FHIR_EXPORT_PATH, get_export_date, slugify

from .constants import LOG_DOCTYPE, QUEUE_DOCTYPE
from .persistence import _store_satusehat_resource_id
from .utils import _json_dumps


def _append_log(queue_name, attempt_number, status, response=None, error=None):
	log = frappe.get_doc(
		{
			"doctype": LOG_DOCTYPE,
			"parent": queue_name,
			"parenttype": QUEUE_DOCTYPE,
			"parentfield": "logs",
			"attempt_number": attempt_number,
			"status": status,
			"attempted_at": now_datetime(),
			"response": response,
			"error": error,
		}
	)
	log.insert(ignore_permissions=True)
	return log.name

def _append_success_ndjson(resource):
	resource_type = resource.get("resourceType", "resource")
	export_folder = FHIR_EXPORT_PATH / get_export_date()
	export_folder.mkdir(parents=True, exist_ok=True)
	file_path = export_folder / f"{slugify(resource_type)}.ndjson"

	with open(file_path, "a", encoding="utf-8") as ndjson:
		ndjson.write(_json_dumps(resource))
		ndjson.write("\n")

	return str(file_path)

def _safe_append_success_ndjson(resource, queue_name):
	try:
		return _append_success_ndjson(resource)
	except Exception:
		frappe.log_error(
			title=f"Khanza SatuSehat NDJSON Write Error: {queue_name}",
			message=frappe.get_traceback(),
		)
		return None

def _safe_store_satusehat_resource_id(queue_doc, fhir, resource_id):
	try:
		_store_satusehat_resource_id(queue_doc, fhir, resource_id)
	except Exception:
		frappe.log_error(
			title=f"Khanza SatuSehat Resource ID Store Error: {queue_doc.name}",
			message=frappe.get_traceback(),
		)
