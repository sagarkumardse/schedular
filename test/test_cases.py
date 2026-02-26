TEST_CASES = [
    # outside working hours + likely schedulable
    {
        "name": "valid_after_hours",
        "command": "Schedule a meeting with john@example.com and sarah@company.com next Tuesday at 9:30 PM for 45 minutes about Q2 planning",
        "history": None,
        "expected_statuses": ["valid", "conflict", "too_soon"]
    },
    # working hours should be blocked
    {
        "name": "blocked_working_hours",
        "command": "Schedule a meeting with john@example.com next Monday at 10am",
        "history": None,
        "expected_statuses": ["not_working_hours"]
    },
    # missing attendees
    {
        "name": "missing_attendees",
        "command": "Schedule meeting tomorrow at 10pm about planning",
        "history": None,
        "expected_statuses": [ "too_soon",'no_attendees']
    },
    # malformed attendee email often ends as no attendees
    {
        "name": "invalid_email_no_domain",
        "command": "Schedule meeting with john@ tomorrow at 11pm",
        "history": None,
        "expected_statuses": ["no_attendees"]
    },
    # history provides attendee email
    {
        "name": "history_supplies_email",
        "command": "Tomorrow at 11:30pm",
        "history": ["Schedule meeting with alex@ai.com"],
        "expected_statuses": ["valid", "conflict", "too_soon"]
    },
    # short/casual phrasing
    {
        "name": "nlp_short_phrase",
        "command": "sarah@company.com Friday 6pm",
        "history": None,
        "expected_statuses": ["valid", "too_soon", "conflict"]
    },
    # explicit too soon
    {
        "name": "too_soon_explicit",
        "command": "Schedule meeting with mike@acme.io today at 11pm",
        "history": None,
        "expected_statuses": ["too_soon", "valid", "not_working_hours"]
    },
    
]
