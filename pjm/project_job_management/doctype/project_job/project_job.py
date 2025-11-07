# Copyright (c) 2025, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, days_diff

class ProjectJob(Document):
	
	def before_save(self):
		# --- Auto-calculate estimated time if not manually entered ---
		if not self.manually_add_time:
			if self.job_start_date and self.estimated_job_end_date:
				self.estimated_time_in_hrs = days_diff(
					self.estimated_job_end_date, self.job_start_date
				) * flt(self.estimated_hours_per_day or 0)
			else:
				self.estimated_time_in_hrs = flt(self.estimated_time_in_hrs or 0)
		else:
			self.estimated_time_in_hrs = flt(self.estimated_time_in_hrs or 0)

		# --- Validate estimated hours ---
		if not self.estimated_time_in_hrs or self.estimated_time_in_hrs <= 0:
			frappe.throw("Estimated Time (hrs) cannot be zero or empty.")

		# --- Calculate unit cost safely ---
		self.unit_cost = flt(self.estimated_project_cost or 0) / flt(self.estimated_time_in_hrs)

		# --- Calculate actual job time from Timesheets ---
		if self.job_status == "Completed":
			job_time = frappe.get_all(
				"Timesheet",
				filters={"project": self.project, "docstatus": 1},
				fields=["sum(total_hours) as total_job_time"]
			)
			self.actual_total_job_time_in_hrs = flt(job_time[0].total_job_time or 0) if job_time else 0
		else:
			self.actual_total_job_time_in_hrs = 0
		
		# --- Calculate overhead & cost ---
		self.calculate_overhead()
		
		# --- Calculate task costs ---
		if self.project:
			self.calculate_task_costs()

	def calculate_task_costs(self):
		"""
		Calculate cost for each task based on timesheet details and employee cost per hour.
		Updates the job_task child table with calculated costs.
		"""
		if not self.project:
			return

		# Get all tasks for the project
		tasks = frappe.get_all(
			"Task",
			filters={
				"project": self.project,
				"status": ["!=", "Cancelled"]
			},
			fields=["name", "subject", "status", "actual_time"]
		)

		if not tasks:
			# Clear job_task table if no tasks
			self.job_task = []
			return

		# Get all submitted timesheets for the project
		timesheets = frappe.get_all(
			"Timesheet",
			filters={
				"parent_project": self.project,
				"docstatus": 1
			},
			fields=["name", "employee"]
		)

		# Create a map of timesheet name to employee
		timesheet_employee_map = {ts.name: ts.employee for ts in timesheets}

		# Get all timesheet details for tasks in this project
		timesheet_detail_list = frappe.get_all(
			"Timesheet Detail",
			filters={
				"project": self.project,
				"task": ["in", [t.name for t in tasks]],
				"parent": ["in", [ts.name for ts in timesheets]],
				"parenttype": "Timesheet"
			},
			fields=["name", "task", "hours", "parent"]
		)

		# Create a map of task to timesheet details with employee info
		task_timesheet_map = {}
		for td in timesheet_detail_list:
			if td.task not in task_timesheet_map:
				task_timesheet_map[td.task] = []
			
			employee = timesheet_employee_map.get(td.parent)
			if employee:
				task_timesheet_map[td.task].append({
					"hours": flt(td.hours or 0),
					"employee": employee
				})

		# Create or update job_task entries
		existing_tasks = {row.task: row for row in self.job_task}
		
		for task in tasks:
			# Calculate total cost for this task
			total_task_cost = 0.0
			task_timesheet_details = task_timesheet_map.get(task.name, [])
			
			for td in task_timesheet_details:
				if td["employee"]:
					# Find employee cost per hour from assigned_employees table
					cost_per_hour = 0.0
					for emp_row in self.assigned_employees or []:
						if emp_row.employee == td["employee"]:
							cost_per_hour = flt(emp_row.cost_per_hour or 0)
							break
					
					total_task_cost += cost_per_hour * td["hours"]

			# Update or create job_task row
			if task.name in existing_tasks:
				row = existing_tasks[task.name]
			else:
				row = self.append("job_task", {})
				row.task = task.name
			
			row.subject = task.subject
			row.status = task.status
			row.actual_time_in_hours = flt(task.actual_time or 0)
			row.cost = total_task_cost

	def calculate_overhead(self):
		"""
		Calculate Overhead Rate per Hour and Total Overhead for Project
		using fields from the same Project Job document.
		"""

		admin_salaries = flt(self.administrator_salaries or 0)
		monthly_expenses = flt(self.company_monthly_expenses or 0)
		total_available_hours = flt(self.available_working_hours_per_month or 0)

		if total_available_hours <= 0:
			frappe.throw("Available Working Hours per Month cannot be zero or empty.")

		# Formula: Overhead Rate per Hour = (Admin Salaries + Monthly Expenses) / Total Hours
		self.overhead_rate_per_hour = (admin_salaries + monthly_expenses) / total_available_hours

		# Formula: Total Overhead = Overhead Rate × Total Hours Spent on Project
		total_hours_spent = flt(self.working_hours or 0)
		self.total_overhead = (self.overhead_rate_per_hour * total_hours_spent)  + self.additional_overhead

		# Formula: Total Working Cost = Total Overhead + Direct Working Cost
		self.total_working_cost = self.total_overhead + flt(self.working_cost or 0)

@frappe.whitelist()
def recalculate_task_costs(doc_name, save=False):
	"""
	Recalculate task costs for a Project Job document.
	Returns the updated job_task data.
	If save=True, saves the document with updated costs.
	"""
	doc = frappe.get_doc("Project Job", doc_name)
	doc.calculate_task_costs()
	
	# Save if requested (but don't save on refresh to avoid triggering save events)
	if save:
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	
	# Return the job_task data
	job_task_data = []
	for row in doc.job_task:
		job_task_data.append({
			"task": row.task,
			"subject": row.subject,
			"status": row.status,
			"actual_time_in_hours": row.actual_time_in_hours,
			"cost": row.cost
		})
	
	return job_task_data
