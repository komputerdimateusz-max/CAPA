# AGENT_TASKS.md — Action-to-Money Tracker

## Now (next 1-2 commits)
1) Actions module hardening
- Add "edit action" (full edit, not only status)
- Add delete (soft delete) + audit fields
- Add validation UI hints (required fields)
- Add export to CSV (from DB)
- Add import from CSV (into DB)

2) Data model upgrades
- Add action_id format (ATM-0001 style)
- Add categories: type (scrap/downtime/quality), area, defect_code, downtime_reason
- Add attachments placeholder (path/url)

## Next
- Create "Action Library" templates + reuse
- Add mapping rules: line + project_or_family required for ROI layer

## Later
- ROI module: before/after windows + savings
- Champions ranking: confidence-weighted €
- PDF report: exec summary
