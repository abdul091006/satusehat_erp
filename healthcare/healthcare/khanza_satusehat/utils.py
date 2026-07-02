import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from .constants import QUEUE_DOCTYPE


def _now():
	return now_datetime()

def _json_dumps(value):
	return json.dumps(value, ensure_ascii=False, default=str)

def _canonical_json(value):
	return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _canonical_source_json(value):
	value = dict(_as_dict(value))
	value.pop("id", None)
	return _canonical_json(value)

def _as_dict(value):
	if isinstance(value, dict):
		return value
	if isinstance(value, str) and value.strip():
		return json.loads(value)
	return {}

def _get_request_payload(kwargs):
	data = {}
	if getattr(frappe.local, "request", None):
		data = frappe.request.get_json(silent=True) or {}
	if not data:
		data = kwargs or {}
	return data.get("payload") or data

def _normalize_method(method):
	method = (method or "POST").upper()
	if method not in ("POST", "PUT"):
		frappe.throw(_("Only POST and PUT are supported for SatuSehat forwarding"))
	return method

def _queue_response(doc, message):
	return {
		"status": "ok",
		"message": message,
		"external_id": doc.external_id,
		"queue_name": doc.name,
		"import_status": getattr(doc, "import_status", None),
		"review_status": getattr(doc, "review_status", None),
		"revision_no": getattr(doc, "revision_no", None),
		"validation_status": getattr(doc, "validation_status", None),
		"approval_status": doc.approval_status,
		"sync_status": doc.sync_status,
		"target_docstatus": getattr(doc, "target_docstatus", None),
		"target_doctype": getattr(doc, "target_doctype", None),
		"target_docname": getattr(doc, "target_docname", None),
		"attempts": doc.attempts,
	}

def _parse_names(value):
	if not value:
		return []
	if isinstance(value, str):
		value = json.loads(value)
	if isinstance(value, (tuple, set)):
		value = list(value)
	return [name for name in value if name]

def _extract_source_payload(payload):
	source = (
		payload.get("source_payload")
		or payload.get("source")
		or payload.get("data")
		or payload
	)
	if isinstance(source, str):
		source = json.loads(source)
	if not isinstance(source, dict):
		frappe.throw(_("Khanza payload must be a JSON object"))
	if not (source.get("resource_type") or source.get("resourceType")):
		frappe.throw(_("Khanza payload requires resource_type or resourceType"))
	return source

def _resource_type(source):
	return source.get("resource_type") or source.get("resourceType")

def _extract_external_id(payload, source):
	resource_type = _resource_type(source)
	parts = [
		payload.get("external_id"),
		source.get("external_id"),
		payload.get("name"),
		source.get("name"),
		source.get("encounter_external_id"),
		source.get("no_rawat"),
		source.get("noorder"),
		source.get("no_resep"),
		source.get("kode_brng"),
		source.get("kd_jenis_prw"),
		source.get("kd_penyakit"),
		source.get("kode"),
		source.get("id"),
	]
	for value in parts:
		if value:
			return str(value)
	return (
		f"{resource_type}-{source.get('id')}"
		if source.get("id")
		else None
	)

def _get_retry_delay(attempts):
	if attempts == 1:
		return timedelta(minutes=1)
	if attempts == 2:
		return timedelta(minutes=5)
	if attempts == 3:
		return timedelta(minutes=10)
	if attempts == 4:
		return timedelta(minutes=15)
	if attempts == 5:
		return timedelta(minutes=15)
	return timedelta(minutes=30)

def _should_retry(last_attempt_at, attempts):
	if not last_attempt_at:
		return True
	last_attempt = get_datetime(last_attempt_at)
	return now_datetime() - last_attempt >= _get_retry_delay(attempts)

def _get_queue_name(external_id=None, queue_name=None):
	if queue_name:
		return queue_name

	if not external_id:
		frappe.throw(_("external_id is required"))

	doc_name = frappe.db.exists(QUEUE_DOCTYPE, {"external_id": external_id})
	if not doc_name:
		frappe.throw(_("Sync record not found"))
	return doc_name

