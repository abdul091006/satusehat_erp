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

def _canonical_fhir_json(value):
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
		frappe.throw(_("Only POST and PUT are supported for SatuSehat FHIR forwarding"))
	return method

def _queue_response(doc, message):
	return {
		"status": "ok",
		"message": message,
		"external_id": doc.external_id,
		"queue_name": doc.name,
		"import_status": getattr(doc, "import_status", None),
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

def _extract_fhir(payload):
	fhir = payload.get("fhir") or payload.get("fhir_payload") or payload.get("data") or payload
	if isinstance(fhir, str):
		fhir = json.loads(fhir)
	if not isinstance(fhir, dict) or not fhir.get("resourceType"):
		frappe.throw(_("FHIR payload with resourceType is required"))
	return fhir

def _extract_external_id(payload, fhir):
	return (
		payload.get("external_id")
		or payload.get("name")
		or payload.get("no_rawat")
		or payload.get("noorder")
		or f"{fhir.get('resourceType')}-{fhir.get('id')}"
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
