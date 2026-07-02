import frappe


def execute():
	doctype = "Khanza SatuSehat Sync Record"
	if not frappe.db.exists("DocType", doctype):
		return

	if "review_status" not in frappe.db.get_table_columns(doctype):
		return

	frappe.db.sql(
		f"""
		UPDATE `tab{doctype}`
		SET review_status = 'Pending'
		WHERE review_status = 'Pending Review'
		"""
	)
