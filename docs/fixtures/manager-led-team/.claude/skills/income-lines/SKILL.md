---
name: income-lines
description: Shared method for reading income lines out of a bank statement or payslip into one table. Use when a worker of the refi-pack-manager team extracts credits, pay amounts or dates from a document, or when asked to "re-read the statement", "redo the income table" or "update the payslip table". Not for judging eligibility or serviceability.
---

# Income lines (shared method)

Every reader on the team uses this method, so two tables can be laid side by side.

1. Copy, never compute. Each row is one line of the document: `date | description | amount | page or payslip`. Write the amount exactly as printed. The reason: a rounded or summed figure cannot be traced back to its line.
2. One table per document, in date order, in the file your brief names.
3. A part you cannot read (an image-only page, a cut-off line) gets no row. List it under `Coverage:` as `NOT RUN` with the reason. Never fill it from a pattern in the other rows; a missing month is a finding, not a gap to smooth over.
4. Totals are the manager's job. Do not add a total row.
