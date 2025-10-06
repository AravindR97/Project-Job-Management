# Copyright (c) 2025, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ProjectJob(Document):
	
	def before_save(self):
		if not self.manually_add_time:
			if self.job_start_date and self.estimated_job_end_date:
				self.estimated_time_in_hrs = frappe.utils.days_diff(self.estimated_job_end_date, self.job_start_date) * self.estimated_hours_per_day
		else:
			self.estimated_time_in_hrs = 0.0

		if self.estimated_time_in_hrs != 0:
			self.unit_cost = self.estimated_project_cost/self.estimated_time_in_hrs
		else:
			frappe.throw("Total Job Time cannot be zero")
