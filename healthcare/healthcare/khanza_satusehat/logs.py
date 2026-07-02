import os
import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path, PureWindowsPath

import frappe
from frappe.utils import now_datetime

from .constants import LOG_DOCTYPE, QUEUE_DOCTYPE
from .persistence import _store_satusehat_resource_id
from .utils import _as_dict, _json_dumps


REVIEW_PARQUET_BASE_PATH = r"C:\Users\ASUS\Documents\Ngoding\dau\pipeline\data\output"


def _host_path(path):
	if os.name == "nt":
		return Path(path)

	windows_path = PureWindowsPath(path)
	if windows_path.drive:
		drive = windows_path.drive.rstrip(":").lower()
		return Path("/mnt") / drive / Path(*windows_path.parts[1:])

	return Path(path)


def _resource_filename(resource_type):
	name = re.sub(r"[^A-Za-z0-9_.-]+", "_", resource_type or "Unknown").strip("._")
	return name or "Unknown"

def _sql_path(path):
	return str(path).replace("\\", "/").replace("'", "''")

def _duckdb_identifier(name):
	return '"' + str(name).replace('"', '""') + '"'

@contextmanager
def _parquet_file_lock(file_path, timeout=30):
	lock_path = file_path.with_suffix(f"{file_path.suffix}.lock")
	deadline = time.monotonic() + timeout
	lock_fd = None

	while lock_fd is None:
		try:
			lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
		except FileExistsError:
			if time.monotonic() >= deadline:
				raise TimeoutError(f"Timed out waiting for Parquet writer lock: {lock_path}")
			time.sleep(0.1)

	try:
		yield
	finally:
		if lock_fd is not None:
			os.close(lock_fd)
		if lock_path.exists():
			lock_path.unlink()


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

def _target_doc_snapshot(target_doc):
	if not target_doc:
		return None

	snapshot = {
		"doctype": target_doc.doctype,
		"name": target_doc.name,
		"docstatus": int(getattr(target_doc, "docstatus", 0) or 0),
		"owner": getattr(target_doc, "owner", None),
		"modified": getattr(target_doc, "modified", None),
	}

	for fieldname in ("patient", "practitioner", "encounter", "company", "status"):
		if target_doc.meta.has_field(fieldname):
			snapshot[fieldname] = target_doc.get(fieldname)

	return snapshot

def _review_event(queue_doc, event_type, target_doc=None, extra=None):
	return {
		"event_type": event_type,
		"event_at": now_datetime(),
		"sync_record": queue_doc.name,
		"external_id": getattr(queue_doc, "external_id", None),
		"resource_type": getattr(queue_doc, "resource_type", None),
		"satusehat_resource_id": getattr(queue_doc, "satusehat_resource_id", None),
		"import_status": getattr(queue_doc, "import_status", None),
		"review_status": getattr(queue_doc, "review_status", None),
		"revision_no": getattr(queue_doc, "revision_no", None),
		"validation_status": getattr(queue_doc, "validation_status", None),
		"validation_summary": getattr(queue_doc, "validation_summary", None),
		"approval_status": getattr(queue_doc, "approval_status", None),
		"sync_status": getattr(queue_doc, "sync_status", None),
		"target_doctype": getattr(queue_doc, "target_doctype", None),
		"target_docname": getattr(queue_doc, "target_docname", None),
		"target_docstatus": getattr(queue_doc, "target_docstatus", None),
		"error_message": getattr(queue_doc, "error_message", None),
		"target_document": _target_doc_snapshot(target_doc),
		"payload": _as_dict(getattr(queue_doc, "payload", None)),
		"source_payload": _as_dict(
			getattr(queue_doc, "source_payload", None)
			or getattr(queue_doc, "fhir_payload", None)
		),
		"fhir_payload": _as_dict(getattr(queue_doc, "fhir_payload", None)),
	}

def _flatten_for_parquet(value, prefix="", output=None):
	output = output if output is not None else {}

	if isinstance(value, dict):
		if not value:
			output[prefix] = "{}"
		for key, child in value.items():
			key = re.sub(r"[^A-Za-z0-9_]+", "_", str(key)).strip("_").lower()
			child_prefix = f"{prefix}__{key}" if prefix else key
			_flatten_for_parquet(child, child_prefix, output)
	elif isinstance(value, list):
		if not value:
			output[prefix] = "[]"
		for idx, child in enumerate(value):
			_flatten_for_parquet(child, f"{prefix}__{idx}", output)
	else:
		output[prefix] = _parquet_scalar(value)

	return output

def _parquet_scalar(value):
	if value is None:
		return None
	if isinstance(value, (bool, int, float, str)):
		return value
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, (datetime, date)):
		return value.isoformat()
	return str(value)

def _row_for_parquet(event):
	row = {
		"event_type": event.get("event_type"),
		"event_at": str(event.get("event_at") or ""),
		"sync_record": event.get("sync_record"),
		"external_id": event.get("external_id"),
		"resource_type": event.get("resource_type"),
		"satusehat_resource_id": event.get("satusehat_resource_id"),
		"import_status": event.get("import_status"),
		"review_status": event.get("review_status"),
		"revision_no": event.get("revision_no"),
		"validation_status": event.get("validation_status"),
		"validation_summary": event.get("validation_summary"),
		"approval_status": event.get("approval_status"),
		"sync_status": event.get("sync_status"),
		"target_doctype": event.get("target_doctype"),
		"target_docname": event.get("target_docname"),
		"target_docstatus": event.get("target_docstatus"),
		"error_message": event.get("error_message"),
		"target_document_json": _json_dumps(event.get("target_document")),
		"payload_json": _json_dumps(event.get("payload")),
		"source_payload_json": _json_dumps(event.get("source_payload")),
		"fhir_payload_json": _json_dumps(event.get("fhir_payload")),
		"extra_json": _json_dumps(event.get("extra")),
	}

	source_payload = event.get("source_payload")
	if source_payload:
		row.update(_flatten_for_parquet(source_payload))

	for key in ("target_document", "payload", "fhir_payload", "extra"):
		value = event.get(key)
		if value:
			row.update(_flatten_for_parquet(value, key))
	return row

def _write_parquet_row(file_path, row):
	try:
		import duckdb
	except ImportError as exc:
		raise RuntimeError(
			"Python package 'duckdb' is required to write review Parquet files. "
			"Run bench setup requirements or install duckdb in the bench environment."
		) from exc

	file_path.parent.mkdir(parents=True, exist_ok=True)
	temp_json = None
	temp_parquet = file_path.with_name(f".{file_path.stem}.{uuid.uuid4().hex}.parquet")
	try:
		with _parquet_file_lock(file_path):
			with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
				handle.write(_json_dumps([row]))
				temp_json = Path(handle.name)

			con = duckdb.connect(":memory:")
			json_path = _sql_path(temp_json)
			out_path = _sql_path(temp_parquet)
			should_append = False
			if file_path.exists():
				in_path = _sql_path(file_path)
				try:
					columns = {
						item[0]
						for item in con.execute(
							f"DESCRIBE SELECT * FROM read_parquet('{in_path}')"
						).fetchall()
					}
					should_append = {"event_type", "sync_record"}.issubset(columns)
				except Exception:
					should_append = False

			if should_append:
				in_path = _sql_path(file_path)
				drop_prefixed_source_columns = [
					column
					for column in columns
					if str(column).startswith("source_payload__")
				]
				if drop_prefixed_source_columns and len(drop_prefixed_source_columns) < len(columns):
					existing_select = (
						"SELECT * EXCLUDE ("
						+ ", ".join(_duckdb_identifier(column) for column in drop_prefixed_source_columns)
						+ f") FROM read_parquet('{in_path}')"
					)
				else:
					existing_select = f"SELECT * FROM read_parquet('{in_path}')"
				con.execute(
					f"""
					COPY (
						{existing_select}
						UNION ALL BY NAME
						SELECT * FROM read_json_auto('{json_path}')
					)
					TO '{out_path}' (FORMAT PARQUET)
					"""
				)
			else:
				con.execute(
					f"""
					COPY (
						SELECT * FROM read_json_auto('{json_path}')
					)
					TO '{out_path}' (FORMAT PARQUET)
					"""
				)
			con.close()
			os.replace(temp_parquet, file_path)
	finally:
		if temp_json and temp_json.exists():
			temp_json.unlink()
		if temp_parquet.exists():
			temp_parquet.unlink()

def _append_review_parquet(queue_doc, event_type, target_doc=None, extra=None):
	resource_type = getattr(queue_doc, "resource_type", None) or "Unknown"
	export_folder = _host_path(REVIEW_PARQUET_BASE_PATH)
	file_path = export_folder / f"{_resource_filename(resource_type)}.parquet"

	event = _review_event(queue_doc, event_type, target_doc=target_doc, extra=extra)
	if extra:
		event["extra"] = extra

	_write_parquet_row(file_path, _row_for_parquet(event))
	return str(file_path)

def _safe_append_review_parquet(queue_doc, event_type, target_doc=None, extra=None):
	try:
		return _append_review_parquet(queue_doc, event_type, target_doc=target_doc, extra=extra)
	except Exception:
		queue_name = getattr(queue_doc, "name", queue_doc)
		frappe.log_error(
			title=f"Khanza SatuSehat Review Parquet Write Error: {queue_name}",
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

