# Client reporting portal

## From stored report to PDF

Create client and report records, then generate the corresponding SACS or TCC PDF through the Flask routes in [app.py](app.py). SQLite stores JSON-backed client/report data; ReportLab draws the exported documents.

The portal combines persistence, HTTP routes, HTML, and PDF layout in one module. Separating calculation rules from drawing code would make business-rule tests and layout changes easier. Review access control and the report formulas before using real client information; the repository does not provide a validated financial-rules test suite.

## What It Does

| Feature | Details |
|---|---|
| **Client Profiles** | Store names, DOB, SSN last-4, account structure once — reused every quarter |
| **Quarterly Data Entry** | Enter live balances (Pinnacle, Schwab, Zillow) with last-quarter values shown as reference |
| **Auto-Calculations** | Inflow − Outflow = Excess; retirement totals per spouse; grand net worth; liabilities separate |
| **SACS PDF** | Cashflow bubble diagram (green Inflow → red Outflow → blue Private Reserve) |
| **TCC PDF** | Net worth overview with retirement, non-retirement, trust, and liabilities sections |
| **Report History** | Re-download any past quarterly report at any time |


### Key Design Decisions (matching the PRD)

- **No API integrations in V1** — all balances entered manually (Pinnacle via email, Schwab manually, Zillow lookup)
- **Liabilities NOT subtracted from net worth** — shown as a separate section per Rebecca's instruction
- **Trust value separate from non-retirement total** — non-retirement total is accounts only, not trust
- **Fixed PDF layout** — nothing shifts regardless of number size
- **SQLite** — sufficient for 6–12 clients with minimal query volume

### Identified Gaps (not in PRD, filled with best judgment)

1. **No authentication** — the PRD specifies a 3-person internal team.
2. **Canva export** — marked as "discussed but not confirmed" in PRD; not included in V1. PDF download is the primary output.
3. **Dropbox auto-save** — also "not confirmed"; not included in V1
4. **Exact pixel-perfect PDF match** — the PRD references specific Canva template screenshots (timestamps 05:18, 13:08, 20:52). The PDF layouts cover the described structure (bubble diagrams, circle charts, correct sections) but may need minor visual tweaks once the team compares against their existing templates.
5. **Insurance deductibles for PR Target** — PRD says target = 6× monthly expenses + all insurance deductibles. The form uses 6× expenses as default; insurance deductibles can be added to the pr_target field manually or as a V1.1 field.
