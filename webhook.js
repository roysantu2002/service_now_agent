(function executeRule(current, previous /*null when async*/) {

    try {
        // ✅ Create a GlideRecord instance for the 'incident' table
        var gr = new GlideRecord('incident');
        gr.addQuery('sys_id', current.getValue('sys_id'));  // Use sys_id from the current record
        gr.query();

        if (!gr.next()) {
            gs.error("❌ No matching incident found for sys_id: " + current.getValue('sys_id'), "CustomOutboundRule");
            return;
        }

        // ✅ Create the REST API request
        var request = new sn_ws.RESTMessageV2();
        request.setEndpoint('https://f5d093723e52.ngrok-free.app/api/v1/webhooks/servicenow/incident-update');
        request.setHttpMethod('POST');

        // Optional: Basic Auth if required
        // request.setBasicAuth('admin', 'admin');

        // Headers
        request.setRequestHeader("Accept", "application/json");
        request.setRequestHeader("Content-Type", "application/json");

        // ✅ Helper functions
        function val(field) {
            return gr.getValue(field) || "";
        }

        function disp(field) {
            return gr[field] ? gr[field].getDisplayValue() : "";
        }

        // ✅ Build payload (ServiceNow-style)
        var payload = {
            result: {
                sys_id: val("sys_id"),
                number: val("number"),
                short_description: val("short_description"),
                description: val("description"),
                priority: val("priority"),
                impact: val("impact"),
                urgency: val("urgency"),
                state: val("state"),
                category: val("category"),
                caller_id: disp("caller_id"),
                opened_by: disp("opened_by"),
                sys_created_on: val("sys_created_on"),
                sys_updated_on: val("sys_updated_on"),
                assignment_group: disp("assignment_group"),
                assigned_to: disp("assigned_to"),
                company: disp("company"),
                made_sla: val("made_sla"),
                knowledge: val("knowledge"),
                reopened_time: val("reopened_time"),
                closed_at: val("closed_at"),
                contact_type: val("contact_type"),
                location: disp("location"),
                reopened_by: disp("reopened_by"),
                parent_incident: disp("parent_incident")
            }
        };

        var requestBody = JSON.stringify(payload);
        request.setRequestBody(requestBody);

        // ✅ Execute REST call
        var response = request.execute();
        var httpStatus = response.getStatusCode();
        var responseBody = response.getBody();

        // ✅ Logging for debugging
        gs.info("✅ Webhook Triggered for Incident: " + gr.number + " [HTTP " + httpStatus + "]", "CustomOutboundRule");
        gs.info("📤 Payload Sent:\n" + requestBody, "CustomOutboundRule");
        gs.info("📥 Response:\n" + responseBody, "CustomOutboundRule");

    } catch (ex) {
        gs.error("❌ Exception in CustomOutboundRule: " + ex.message, "CustomOutboundRule");
    }

})(current, previous);
