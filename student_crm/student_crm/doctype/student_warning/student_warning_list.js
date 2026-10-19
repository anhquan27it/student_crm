
frappe.listview_settings['Student Warning'] = {
    add_fields: ['is_active', 'status'],
    get_indicator(doc) {
        return doc.is_active ? [__('Threshold Exceeded'), 'red', 'is_active,=,1'] : [__('Below Threshold'), 'green', 'is_active,=,0'];
    }
};
