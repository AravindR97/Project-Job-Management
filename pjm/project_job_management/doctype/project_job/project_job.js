// Copyright (c) 2025, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Job", {
    async refresh(frm) {
        if (frm._just_saved) {
            delete frm._just_saved;
            return;
        }

        update_timesheet_summary(frm);
        update_employee_totals(frm);
        calculate_estimated_time(frm);

        if (!frm.is_new() && frm.doc.project) {
            try {
                // Update billed invoice amount from Project
                const billed = await frappe.db.get_value("Project", frm.doc.project, "total_billed_amount");
                const billed_amount = billed?.message?.total_billed_amount || 0;

                if (frm.doc.billed_invoice_amount !== billed_amount) {
                    frm.doc.billed_invoice_amount = billed_amount;
                    frm.refresh_field("billed_invoice_amount");
                }

                // Update purchase amount and journal expense by reloading Project Job
                // This ensures we get the latest calculated values
                const project_job_data = await frappe.db.get_value("Project Job", frm.doc.name, [
                    "purchase_amount",
                    "journal_expense"
                ]);

                if (project_job_data?.message) {
                    const purchase_amount = project_job_data.message.purchase_amount || 0;
                    const journal_expense = project_job_data.message.journal_expense || 0;

                    if (frm.doc.purchase_amount !== purchase_amount) {
                        frm.doc.purchase_amount = purchase_amount;
                        frm.refresh_field("purchase_amount");
                    }

                    if (frm.doc.journal_expense !== journal_expense) {
                        frm.doc.journal_expense = journal_expense;
                        frm.refresh_field("journal_expense");
                    }
                }
            } catch (error) {
                console.error("Failed to fetch financial amounts", error);
            }
        }
    },

    job_timesheets_add: async function (frm, cdt, cdn) {
        await frappe.model.set_value(cdt, cdn, "hourly_cost", 0);
        await frappe.model.set_value(cdt, cdn, "working_cost", 0);
        update_timesheet_summary(frm);
        update_employee_totals(frm);
    },

    job_timesheets_remove(frm) {
        update_timesheet_summary(frm);
        update_employee_totals(frm);
    },

    after_save(frm) {
        frm._just_saved = true;
        setTimeout(() => {
            frm.reload_doc();
        }, 100);
    },

    estimated_project_cost(frm) {
        calculate_estimated_time(frm);
    },

    unit_cost(frm) {
        calculate_estimated_time(frm);
    }
});

frappe.ui.form.on("Job Timesheet Item", {
    async employee(frm, cdt, cdn) {
        await update_timesheet_row_costs(frm, cdt, cdn);
        update_employee_totals(frm);
    },

    async working_hours(frm, cdt, cdn) {
        await update_timesheet_working_cost(frm, cdt, cdn);
        update_employee_totals(frm);
    }
});

const to_flt = (value) => {
    const val = value ?? 0;
    const hasFrappeFlt =
        typeof frappe !== "undefined" &&
        frappe.utils &&
        typeof frappe.utils.flt === "function";

    if (hasFrappeFlt) {
        return frappe.utils.flt(val);
    }

    const numeric = typeof val === "number" ? val : parseFloat(val);
    return Number.isFinite(numeric) ? numeric : 0;
};

const get_timesheet_row = (cdt, cdn) => (locals[cdt] && locals[cdt][cdn]) || null;

const get_employee_hourly_cost = (frm, employee) => {
    if (!employee) {
        return 0;
    }

    const assignment = (frm.doc.assigned_employees || []).find((row) => row.employee === employee);
    return assignment ? to_flt(assignment.cost_per_hour) : 0;
};

const update_timesheet_row_costs = async (frm, cdt, cdn) => {
    const row = get_timesheet_row(cdt, cdn);
    if (!row) {
        return;
    }

    const hourly_cost = get_employee_hourly_cost(frm, row.employee);
    await frappe.model.set_value(cdt, cdn, "hourly_cost", hourly_cost);
    await update_timesheet_working_cost(frm, cdt, cdn);
};

const update_timesheet_working_cost = async (frm, cdt, cdn) => {
    const row = get_timesheet_row(cdt, cdn);
    if (!row) {
        return;
    }

    const hourly_cost = to_flt(row.hourly_cost);
    const working_hours = to_flt(row.working_hours);
    const working_cost = hourly_cost * working_hours;

    await frappe.model.set_value(cdt, cdn, "working_cost", working_cost);
    update_timesheet_summary(frm);
};

const update_timesheet_summary = (frm) => {
    const rows = frm.doc.job_timesheets || [];

    let total_hours = 0;
    let total_cost = 0;

    rows.forEach((row) => {
        total_hours += to_flt(row.working_hours);
        total_cost += to_flt(row.working_cost);
    });

    const current_hours = to_flt(frm.doc.working_hours);
    const current_cost = to_flt(frm.doc.working_cost);

    const hours_changed = Math.abs(current_hours - total_hours) > 0.0001;
    const cost_changed = Math.abs(current_cost - total_cost) > 0.01;

    if (!hours_changed && !cost_changed) {
        frm.refresh_field("working_hours");
        frm.refresh_field("working_cost");
        return;
    }

    if (hours_changed) {
        frm.doc.working_hours = total_hours;
    }

    if (cost_changed) {
        frm.doc.working_cost = total_cost;
    }

    frm.refresh_field("working_hours");
    frm.refresh_field("working_cost");

    if (typeof frm.dirty === "function") {
        frm.dirty();
    } else {
        frm.doc.__unsaved = 1;
    }
};

const calculate_estimated_time = (frm) => {
    const estimated_project_cost = to_flt(frm.doc.estimated_project_cost);
    const unit_cost = to_flt(frm.doc.unit_cost);

    if (unit_cost === 0 || !unit_cost) {
        // Don't calculate if unit_cost is zero or empty
        return;
    }

    const estimated_time_in_hrs = estimated_project_cost / unit_cost;
    const current_estimated_time = to_flt(frm.doc.estimated_time_in_hrs);

    if (Math.abs(current_estimated_time - estimated_time_in_hrs) > 0.0001) {
        frm.doc.estimated_time_in_hrs = estimated_time_in_hrs;
        frm.refresh_field("estimated_time_in_hrs");
        
        if (typeof frm.dirty === "function") {
            frm.dirty();
        } else {
            frm.doc.__unsaved = 1;
        }
    }
};

const update_employee_totals = (frm) => {
    const timesheet_rows = frm.doc.job_timesheets || [];
    const employee_rows = frm.doc.assigned_employees || [];

    // Calculate totals for each employee from timesheets
    const employee_totals = {};
    
    timesheet_rows.forEach((ts_row) => {
        const employee = ts_row.employee;
        if (!employee) return;

        if (!employee_totals[employee]) {
            employee_totals[employee] = {
                total_hours: 0,
                total_cost: 0
            };
        }

        employee_totals[employee].total_hours += to_flt(ts_row.working_hours);
        employee_totals[employee].total_cost += to_flt(ts_row.working_cost);
    });

    // Update assigned_employees table with calculated totals
    let has_changes = false;
    employee_rows.forEach((emp_row) => {
        const employee = emp_row.employee;
        if (!employee) return;

        const totals = employee_totals[employee] || { total_hours: 0, total_cost: 0 };
        
        const current_hours = to_flt(emp_row.total_working_hours);
        const current_cost = to_flt(emp_row.total_working_cost);
        
        const hours_changed = Math.abs(current_hours - totals.total_hours) > 0.0001;
        const cost_changed = Math.abs(current_cost - totals.total_cost) > 0.01;

        if (hours_changed || cost_changed) {
            if (hours_changed) {
                emp_row.total_working_hours = totals.total_hours;
            }
            if (cost_changed) {
                emp_row.total_working_cost = totals.total_cost;
            }
            has_changes = true;
        }
    });

    // Also set totals to 0 for employees not in timesheets
    employee_rows.forEach((emp_row) => {
        const employee = emp_row.employee;
        if (!employee) return;

        if (!employee_totals[employee]) {
            const current_hours = to_flt(emp_row.total_working_hours);
            const current_cost = to_flt(emp_row.total_working_cost);
            
            if (current_hours !== 0 || current_cost !== 0) {
                emp_row.total_working_hours = 0;
                emp_row.total_working_cost = 0;
                has_changes = true;
            }
        }
    });

    if (has_changes) {
        frm.refresh_field("assigned_employees");
        if (typeof frm.dirty === "function") {
            frm.dirty();
        } else {
            frm.doc.__unsaved = 1;
        }
    }
};
