"""PDFs are checked on structure and text content, not pixels."""

from io import BytesIO

from pypdf import PdfReader

from portal.pdf import build_sacs_pdf, build_tcc_pdf

CLIENT = {"name_1": "Dana Whitfield", "name_2": "Sam Whitfield", "dob_1": "1971-04-02", "ssn_1": "4821"}
REPORT = {
    "quarter": "Q3",
    "year": 2026,
    "inflow": 15000,
    "outflow": 11000,
    "private_reserve_balance": "48000",
    "private_reserve_target": 66000,
    "pinnacle_checking": "6200",
    "pinnacle_savings": "9100",
    "schwab_balance": "210000",
    "schwab_cash": "3100",
    "retirement_1": [{"type": "401K", "acct_num": "1182", "balance": "412000"}],
    "retirement_2": [{"type": "Roth IRA", "acct_num": "7731", "balance": "96000"}],
    "non_retirement": [{"type": "Joint Brokerage", "acct_num": "5520", "balance": "150000", "cash": "4000"}],
    "trust_value": "685000",
    "trust_address": "14 Juniper Lane",
    "liabilities": [{"type": "Mortgage", "rate": "3.1", "balance": "212000"}],
}


def read(buf):
    reader = PdfReader(BytesIO(buf.getvalue()))
    return reader, [page.extract_text() for page in reader.pages]


def test_sacs_has_two_letter_pages_with_figures():
    reader, pages = read(build_sacs_pdf(CLIENT, REPORT))
    assert len(pages) == 2
    box = reader.pages[0].mediabox
    assert (round(box.width), round(box.height)) == (612, 792)
    assert "Dana Whitfield & Sam Whitfield" in pages[0]
    assert "Q3 2026" in pages[0]
    assert "$4,000/mo" in pages[0]
    assert "$66,000" in pages[0]
    assert "Total Liquid Assets" in pages[1]
    assert "$63,300" in pages[1]
    assert reader.metadata.title == "SACS - Dana Whitfield & Sam Whitfield"


def test_tcc_totals_and_masked_identifiers():
    _, pages = read(build_tcc_pdf(CLIENT, REPORT))
    text = "\n".join(pages)
    assert "Grand Total Net Worth" in text
    assert "$1,343,000" in text
    assert "$212,000" in text
    assert "xxx-xx-4821" in text
    assert "acct ...1182" in text


def test_pdfs_render_with_empty_report():
    for build in (build_sacs_pdf, build_tcc_pdf):
        _, pages = read(build({"name_1": "Solo"}, {}))
        assert pages and "Solo" in pages[0]


def test_tcc_flows_onto_continuation_pages_without_dropping_totals():
    many = [{"type": "401K", "acct_num": f"{i:04d}", "balance": "1000"} for i in range(8)]
    report = {
        **REPORT,
        "retirement_1": many,
        "retirement_2": many,
        "non_retirement": [{"type": "Brokerage", "balance": "500"}] * 6,
        "liabilities": [{"type": "HELOC", "rate": "", "balance": "100"}] * 6,
    }
    reader, pages = read(build_tcc_pdf(CLIENT, report))
    assert len(pages) >= 2
    assert "(continued)" in pages[1]
    text = "\n".join(pages)
    assert "Total Liabilities (not subtracted from net worth)" in text
    assert "$600" in text
    assert "Rate: N/A" in text
    # Every page, including continuations, keeps its footer.
    assert all("Confidential" in p for p in pages)


def test_typical_household_fits_on_one_tcc_page():
    _, pages = read(build_tcc_pdf(CLIENT, REPORT))
    assert len(pages) == 1
    assert "Rate: 3.1%" in pages[0]
