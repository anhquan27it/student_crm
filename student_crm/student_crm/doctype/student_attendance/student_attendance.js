frappe.ui.form.on('Student Attendance', {
    refresh(frm) {
        frm.set_intro(__('Record every eligible student before finalizing the session. Only Absent counts as missed slots; Present and Late count as attended. Unfinalize the session before corrections.'));
    }
});
