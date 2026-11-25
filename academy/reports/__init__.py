"""Report projections (``docs/reports.md``).

One module owns every number: the API views and the CSV export read the same annotations, so a
column cannot mean one thing on screen and another in the file. Nothing here writes; the only
side effect is the export's audit row, which the view adds in the caller's transaction.
"""
