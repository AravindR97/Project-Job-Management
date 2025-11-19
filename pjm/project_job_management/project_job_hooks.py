# Copyright (c) 2025, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe


def update_project_job_on_purchase_invoice(doc, method):
	"""Update Project Job financials when Purchase Invoice is submitted or cancelled."""
	_update_project_job(doc.project)


def update_project_job_on_journal_entry(doc, method):
	"""Update Project Job financials when Journal Entry is submitted or cancelled."""
	# Journal Entry has project at account level, not document level
	# Get all unique projects from the accounts
	projects = set()
	if hasattr(doc, "accounts") and doc.accounts:
		for account in doc.accounts:
			if account.project:
				projects.add(account.project)
	
	# Update Project Jobs for all projects found in the accounts
	for project in projects:
		_update_project_job(project)


def _update_project_job(project):
	"""Helper function to update Project Job financials."""
	if not project:
		return
	
	project_job = frappe.db.get_value("Project Job", {"project": project}, "name")
	if not project_job:
		return
	
	project_job_doc = frappe.get_doc("Project Job", project_job)
	project_job_doc.update_project_financials()
	project_job_doc.calculate_total_working_cost()
	project_job_doc.calculate_profit()
	project_job_doc.save(ignore_permissions=True)

