# Macro-Finance Data Pipelines

Python code I wrote as a summer research assistant to Professor Moritz Lenel (Princeton Economics) in 2025. The scripts build quarterly series on who holds U.S. Treasury and agency securities and on repo market activity, from Federal Reserve, BEA, New York Fed, and CRSP data.

No data is included. Every input is either public (Federal Reserve, BEA, New York Fed, FRED) or licensed (CRSP via WRDS), and the sections below say where to get each file.

## Contents

| Folder | Script | What it does |
| --- | --- | --- |
| `financial_accounts/` | `main.py` | Reads a Financial Accounts (Z.1) table and its data dictionary, rebuilds the table's hierarchy of liabilities and holders, and writes each sector's holdings as a quarterly series, in levels and as a share of GDP. Works for table L.210 (Treasury securities) and L.211 (agency- and GSE-backed securities). |
| `financial_accounts/early_draft/` | `data_loader.py`, `hierarchy_parser.py`, `report_generator.py` | An earlier version that parsed the table structure from the Z.1 PDF text and printed a one-quarter summary with consistency checks. Kept to show how the pipeline developed. |
| `repo_market/` | `process_repo.py` | Cleans daily New York Fed tri-party repo data and writes monthly, quarterly-average, and end-of-quarter totals. |
| `repo_market/` | `RRPON_quarterly_avg.py` | Converts the Fed's daily overnight reverse repo series (FRED: RRPONTTLD) to quarterly averages, to match the quarterly Financial Accounts. |
| `treasury_reconciliation/` | `treasury_reconciliation.py` | Pulls security-level Treasury data from CRSP through WRDS, sums market values across securities each day, and compares the quarter-end total with the Dallas Fed's market value of marketable Treasury debt (FRED: MVMTD027MNFRBDAL). Writes a reconciliation table and chart. |

## Setup

```bash
pip install -r requirements.txt
```

`treasury_reconciliation.py` also needs a WRDS account with CRSP access. It asks for your WRDS username and password when it runs and does not store them.

## Usage

### Financial Accounts holdings by sector

```bash
python financial_accounts/main.py <z1_table_csv> <data_dictionary_txt> <gdp_csv> <output_csv>
```

- `z1_table_csv`, `data_dictionary_txt`: a table and its dictionary from the Federal Reserve's [Z.1 data download program](https://www.federalreserve.gov/datadownload/). The file names must contain `210` or `211` so the script can tell which table it is reading.
- `gdp_csv`: quarterly nominal GDP from BEA NIPA Table 1.1.5 (T10105).
- Output: `<output_csv>` with total liabilities, total assets, each holding sector, and the instrument discrepancy, plus `<output_csv>_pct_gdp.csv` with the same series divided by GDP.

### Tri-party repo volumes

```bash
cd repo_market
python process_repo.py              # reads repo_data.csv (New York Fed tri-party repo data)
python RRPON_quarterly_avg.py       # reads RRPONTTLD.csv (FRED download)
```

### CRSP and FRED reconciliation

```bash
python treasury_reconciliation/treasury_reconciliation.py
```

Writes `treasury_reconciliation.csv` and `treasury_reconciliation_plot.png`.

## Design notes

- Mixed frequencies: the repo data is daily and the Financial Accounts are quarterly. The scripts produce both quarterly averages and end-of-quarter values, so the choice can be changed later. Quarter-end repo volumes are volatile for regulatory reasons, which is why averages were the default.
- Units: CRSP reports face value outstanding in millions of dollars and prices per $100 of face value; Z.1 levels are in millions of dollars; BEA NIPA Table 1.1.5 is in billions. The scripts convert to common units before taking ratios or differences.
- The Financial Accounts script finds the relevant rows by their descriptions in the data dictionary rather than by hard-coded series codes. The same code therefore handles both L.210 and L.211, and still works when the Fed adds or renames sectors.
