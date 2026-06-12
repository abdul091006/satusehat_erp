import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class KhanzaSatuSehatQueue(Document):
	def before_insert(self):
		self.source_system = self.source_system or "khanza"
		self.import_status = self.import_status or "pending"
		self.approval_status = self.approval_status or "Pending"
		self.sync_status = self.sync_status or "pending"
		self.attempts = self.attempts or 0

	def validate(self):
		if self.approval_status == "Approved" and not self.approved_at:
			self.approved_by = frappe.session.user
			self.approved_at = now_datetime()
