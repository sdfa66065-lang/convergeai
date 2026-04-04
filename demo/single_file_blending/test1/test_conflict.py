def distill_context(ticket_id: str, target_ref: str):
    log_telemetry("distill_context_called", ticket_id)
    if cache.exists(ticket_id):
        return cache.get(ticket_id)
    jira_payload = fetch_jira_payload(ticket_id)
    github_payload = fetch_github_payload(target_ref)
    return jira_payload, github_payload
