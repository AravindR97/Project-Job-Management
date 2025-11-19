# Copyright (c) 2025, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ProjectJob(Document):

	def before_save(self):
		cost_per_hr = flt(self.unit_cost or 0)
		if cost_per_hr > 0:
			self.estimated_time_in_hrs = flt(self.estimated_project_cost or 0) / cost_per_hr

		# --- Calculate overhead & cost ---
		self.calculate_overhead()

		# --- Calculate employee totals from timesheets ---
		self.calculate_employee_totals()

		# --- Calculate project-linked financials (PI & JE) ---
		self.update_project_financials()
		
		# --- Calculate total working cost ---
		self.calculate_total_working_cost()
		
		# --- Calculate profit ---
		self.calculate_profit()

	def calculate_overhead(self):
		"""
		Calculate Overhead Rate per Hour and Total Overhead for Project
		using fields from the same Project Job document.
		"""

		admin_salaries = flt(self.administrator_salaries or 0)
		monthly_expenses = flt(self.company_monthly_expenses or 0)
		total_available_hours = flt(self.available_working_hours_per_month or 0)


		overhead_rate = flt(self.overhead_rate_per_hour or 0)
		if total_available_hours > 0:
			# Formula: Overhead Rate per Hour = (Admin Salaries + Monthly Expenses) / Total Hours
			overhead_rate = (admin_salaries + monthly_expenses) / total_available_hours

		self.overhead_rate_per_hour = overhead_rate

		# Formula: Total Overhead = Overhead Rate × Total Hours Spent on Project
		total_hours_spent = flt(self.working_hours or 0)
		self.total_overhead = (overhead_rate * total_hours_spent) + flt(self.additional_overhead or 0)

	def calculate_employee_totals(self):
		"""
		Calculate total_working_hours and total_working_cost for each employee
		from the job_timesheets table and update assigned_employees table.
		"""
		if not self.assigned_employees or not self.job_timesheets:
			# If no employees or timesheets, set all totals to 0
			if self.assigned_employees:
				for emp_row in self.assigned_employees:
					emp_row.total_working_hours = 0
					emp_row.total_working_cost = 0
			return

		# Calculate totals for each employee from timesheets
		employee_totals = {}
		
		for ts_row in self.job_timesheets:
			employee = ts_row.employee
			if not employee:
				continue

			if employee not in employee_totals:
				employee_totals[employee] = {
					"total_hours": 0.0,
					"total_cost": 0.0
				}

			employee_totals[employee]["total_hours"] += flt(ts_row.working_hours or 0)
			employee_totals[employee]["total_cost"] += flt(ts_row.working_cost or 0)

		# Update assigned_employees table with calculated totals
		for emp_row in self.assigned_employees:
			employee = emp_row.employee
			if not employee:
				continue

			totals = employee_totals.get(employee, {"total_hours": 0.0, "total_cost": 0.0})
			emp_row.total_working_hours = totals["total_hours"]
			emp_row.total_working_cost = totals["total_cost"]

	def update_project_financials(self):
		"""
		Calculate purchase cost from Purchase Invoices and
		total expense from Journal Entries linked with this Project.
		Values are stored on the Project Job as read-only fields.
		"""
		if not self.project:
			self.purchase_amount = 0
			self.journal_expense = 0
			return

		self.purchase_amount = self.get_purchase_amount_from_pi()
		self.journal_expense = self.get_expense_from_journal_entries()

	def calculate_total_working_cost(self):
		"""
		Calculate Total Working Cost = Working Cost + Journal Expense + Purchase Amount + Total Overhead
		"""
		working_cost = flt(self.working_cost or 0)
		journal_expense = flt(self.journal_expense or 0)
		purchase_amount = flt(self.purchase_amount or 0)
		total_overhead = flt(self.total_overhead or 0)
		
		self.total_working_cost = working_cost + journal_expense + purchase_amount + total_overhead

	def get_purchase_amount_from_pi(self) -> float:
		"""Sum of Purchase Invoice base grand total linked to this Project."""
		result = frappe.db.sql(
			"""
			SELECT SUM(base_grand_total) AS total
			FROM `tabPurchase Invoice`
			WHERE project = %s AND docstatus = 1
			""",
			self.project,
			as_dict=True,
		)

		return flt(result[0].get("total")) if result and result[0].get("total") else 0.0

	def get_expense_from_journal_entries(self) -> float:
		"""
		Total Expense from Journal Entries linked with this Project.

		We use GL Entry so that only posted (submitted) entries are considered,
		and we restrict to Expense accounts.
		"""
		result = frappe.db.sql(
			"""
			SELECT SUM(gle.debit - gle.credit) AS total
			FROM `tabGL Entry` gle
			JOIN `tabAccount` acc ON gle.account = acc.name
			WHERE gle.project = %s
			  AND gle.voucher_type = 'Journal Entry'
			  AND gle.is_cancelled = 0
			  AND acc.root_type = 'Expense'
			""",
			self.project,
			as_dict=True,
		)

		return flt(result[0].get("total")) if result and result[0].get("total") else 0.0

	def calculate_profit(self):
		"""
		Calculate profit: Billed Invoice Amount - Total Working Cost
		Total Working Cost includes Working Cost + Journal Expense + Purchase Amount + Total Overhead
		"""
		billed_amount = flt(self.billed_invoice_amount or 0)
		total_working_cost = flt(self.total_working_cost or 0)
		
		self.profit = billed_amount - total_working_cost

