import frappe


OLD_DOCTYPE = "Khanza SatuSehat Queue"
NEW_DOCTYPE = "Khanza SatuSehat Sync Record"
SOURCE_FIELDNAME = "khanza_queue"
SOURCE_LABEL = "Source Sync Record"


def execute():
	if frappe.db.exists("DocType", OLD_DOCTYPE) and not frappe.db.exists("DocType", NEW_DOCTYPE):
		frappe.rename_doc("DocType", OLD_DOCTYPE, NEW_DOCTYPE, force=True)

	_update_link_fields()
	_update_child_parenttype()


def _update_link_fields():
	for table in ("DocField", "Custom Field"):
		frappe.db.sql(
			f"""
			UPDATE `tab{table}`
			SET options = %s, label = %s
			WHERE fieldname = %s
			  AND options IN (%s, %s)
			""",
			(NEW_DOCTYPE, SOURCE_LABEL, SOURCE_FIELDNAME, OLD_DOCTYPE, NEW_DOCTYPE),
		)


def _update_child_parenttype():
	if not frappe.db.table_exists("Khanza SatuSehat Sync Log"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabKhanza SatuSehat Sync Log`
		SET parenttype = %s
		WHERE parenttype = %s
		""",
		(NEW_DOCTYPE, OLD_DOCTYPE),
	)
