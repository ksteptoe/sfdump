# Testing and CI

Guidelines for automated validation.

## Unit Tests

Recommended tests:

- API wrapper behaviour
- Chunk slicing logic
- Resume detection
- Missing-file detection
- Retry behaviour
- Redaction mapping
- Index building

## CI Recommendations

- Run full export against a test org with synthetic attachments
- Validate report generation
- Ensure redacted output contains no IDs
- Ensure unredacted output is correctly excluded via `.gitignore`
