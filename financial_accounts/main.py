import sys
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

# --- Configuration for Different File Types ---
CONFIG = {
    'l210': {
        'liabilities_desc': 'federal government; treasury securities; liability',
        'assets_desc': 'all sectors; treasury securities; asset',
        'discrepancy_desc': 'discrepancy (market value)',
        'end_of_assets_marker': 'nonmarketable',
    },
    'l211': {
        'liabilities_desc': 'all sectors; u.s. government agency securities; liability',
        'assets_desc': 'all sectors; agency- and gse-backed securities; asset',
        'discrepancy_desc': 'instrument discrepancies',
    }
}


# --- Data Structures ---

@dataclass
class TreasuryItem:
    """Represents a single line item from the report's hierarchy."""
    id: str
    description: str
    full_description: str
    children: List['TreasuryItem'] = field(default_factory=list)

@dataclass
class TreasuryData:
    """Holds all the hierarchical data extracted from the data dictionary."""
    items_by_id: Dict[str, TreasuryItem] = field(default_factory=dict)
    total_liabilities: Optional[TreasuryItem] = None
    total_assets: Optional[TreasuryItem] = None
    discrepancy: Optional[TreasuryItem] = None
    asset_holders: List[TreasuryItem] = field(default_factory=list)

# --- Data Loading and Parsing ---

def extract_hierarchy_from_dictionary(dictionary_path: str, latest_data: pd.Series, config: dict) -> TreasuryData:
    """
    Parses the data dictionary text file to build the instrument hierarchy using the provided config.
    """
    data = TreasuryData()
    all_items: List[TreasuryItem] = []

    with open(dictionary_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 2:
                continue
            item_id = parts[0].split('.')[0]
            full_desc = parts[1]
            core_desc = full_desc.split(';')[0].strip()
            item = TreasuryItem(id=item_id, description=core_desc, full_description=full_desc)
            data.items_by_id[item_id] = item
            all_items.append(item)

    liab_desc = config['liabilities_desc']
    asset_desc = config['assets_desc']
    disc_desc = config['discrepancy_desc']

    for itm in all_items:
        d = itm.full_description.lower()
        if d.startswith(liab_desc):
            data.total_liabilities = itm
        elif d.startswith(asset_desc):
            data.total_assets = itm
        elif d.startswith(disc_desc):
            data.discrepancy = itm

    if not data.total_liabilities or not data.total_assets:
        return data

    liab_idx = all_items.index(data.total_liabilities)
    asset_idx = all_items.index(data.total_assets)

    # Determine the end of the asset block using config
    end_idx = len(all_items)
    if config.get('end_of_assets_marker'):
        marker_text = config['end_of_assets_marker']
        memo_item = next((x for x in all_items if marker_text in x.full_description.lower()), None)
        if memo_item:
            end_idx = all_items.index(memo_item)

    asset_block = all_items[asset_idx+1:end_idx]
    data.total_liabilities.children = all_items[liab_idx+1:asset_idx]

    groups: Dict[str, List[TreasuryItem]] = defaultdict(list)
    for itm in asset_block:
        if data.discrepancy and itm.id == data.discrepancy.id:
            continue
        groups[itm.id[:9]].append(itm)

    top_assets: List[TreasuryItem] = []
    for items in groups.values():
        if len(items) == 1:
            top_assets.append(items[0])
        else:
            parent = max(items, key=lambda x: latest_data.get(x.id, 0.0))
            top_assets.append(parent)
            for child in items:
                if child.id != parent.id:
                    parent.children.append(child)

    if data.discrepancy:
        top_assets.append(data.discrepancy)
    data.asset_holders = top_assets

    return data


def load_csv_dataframe(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.set_index('date', inplace=True)
    df.columns = [c.split('.')[0] for c in df.columns]
    df = df.apply(pd.to_numeric, errors='coerce').fillna(0)
    return df

# --- GDP Percentage Logic ---

def add_gdp_pct(df: pd.DataFrame, gdp_csv_path: str) -> pd.DataFrame:
    raw = pd.read_csv(gdp_csv_path, header=None, encoding='utf-8-sig')

    col0 = raw.iloc[:, 0].astype(str).str.strip().str.lower()
    if not col0.eq('line').any():
        raise ValueError("Could not locate header row (first column 'Line') in GDP CSV")
    header_idx = col0[col0.eq('line')].index[0]
    header = raw.iloc[header_idx]

    descs = raw.iloc[:, 1].astype(str).str.strip().str.lower()
    if not descs.eq('gross domestic product').any():
        raise ValueError("Could not find 'Gross domestic product' row in GDP CSV")
    gdp_idx = descs[descs.eq('gross domestic product')].idxmax()

    gdp_row = raw.iloc[gdp_idx]
    start_col = -1
    for i in range(2, len(gdp_row)):
        try:
            float(str(gdp_row[i]).replace(',', '').strip())
            start_col = i
            break
        except (ValueError, TypeError):
            continue

    if start_col == -1:
        raise ValueError("Could not find any numeric values in the GDP data row.")

    gdp_raw_vals_full = gdp_row.iloc[start_col:].tolist()
    raw_quarters_full = header.iloc[start_col:].tolist()

    num_points = min(len(gdp_raw_vals_full), len(raw_quarters_full))
    gdp_raw_vals = gdp_raw_vals_full[:num_points]
    raw_quarters = raw_quarters_full[:num_points]

    quarters = [str(q).replace(':','').replace(' ','').upper().strip() for q in raw_quarters]

    gdp_vals = [float(str(v).replace(',','').strip()) if v else float('nan') for v in gdp_raw_vals]

    gdp_series = pd.Series(data=gdp_vals, index=quarters)

    df2 = df.copy()
    norm_idx = [idx.replace(':','').upper() for idx in df2.index]
    df2['gdp_musd'] = [gdp_series.get(q, float('nan')) for q in norm_idx]

    df2.dropna(subset=['gdp_musd'], inplace=True)
    if df2.empty:
        raise ValueError("No matching quarters found between data and GDP file.")

    value_cols = [c for c in df2.columns if c != 'gdp_musd']
    dec = df2[value_cols].div(df2['gdp_musd'], axis=0)
    dec.columns = [f'{c}_pct_gdp' for c in value_cols]

    return dec

# --- CSV Generation ---

def generate_output_df(hierarchy_data: TreasuryData, hist: pd.DataFrame) -> pd.DataFrame:
    """
    Generates the final output DataFrame based on the parsed hierarchy.
    """
    if not hierarchy_data.total_liabilities or not hierarchy_data.total_assets:
        raise ValueError("Missing liabilities/assets hierarchy data.")

    out = pd.DataFrame(index=hist.index)

    # Add Total Liabilities and Assets first
    out['Total Liabilities'] = hist[hierarchy_data.total_liabilities.id]
    out['Total Assets'] = hist[hierarchy_data.total_assets.id]

    # Get all asset holders EXCEPT the discrepancy
    discrepancy_id = hierarchy_data.discrepancy.id if hierarchy_data.discrepancy else None
    main_holders = [h for h in hierarchy_data.asset_holders if h.id != discrepancy_id]

    # Add main asset holders to the output, sorted by their original file position
    items_by_id_order = list(hierarchy_data.items_by_id.values())
    for itm in sorted(main_holders, key=lambda x: items_by_id_order.index(x)):
        if itm.id in hist.columns:
            out[itm.description] = hist[itm.id]

    # Add the discrepancy last among the components
    if discrepancy_id and discrepancy_id in hist.columns:
        out[hierarchy_data.discrepancy.description] = hist[discrepancy_id]

    # Calculate the sum of main components correctly
    main_holder_ids = [h.id for h in main_holders]
    if main_holder_ids:
        out['Sum of Asset Components'] = hist[main_holder_ids].sum(axis=1)
    else:
        out['Sum of Asset Components'] = 0

    return out

# --- Main Execution ---

def main(csv_path: str, dict_path: str, gdp_path: str, output_path: str):
    """
    Main function to run the data processing and report generation pipeline.
    """
    if '210' in csv_path.lower() or '210' in dict_path.lower():
        file_type_config = CONFIG['l210']
        print("Detected L210 (Treasury Securities) input.")
    elif '211' in csv_path.lower() or '211' in dict_path.lower():
        file_type_config = CONFIG['l211']
        print("Detected L211 (Agency and GSE-Backed Securities) input.")
    else:
        raise ValueError("Could not determine file type from input paths. Expecting 'l210' or 'l211' in filenames.")

    hist = load_csv_dataframe(csv_path)
    latest = hist.iloc[-1]
    hierarchy = extract_hierarchy_from_dictionary(dict_path, latest, file_type_config)

    base = generate_output_df(hierarchy, hist)
    base.to_csv(output_path)
    print(f"Base report saved to: {output_path}")

    try:
        dec = add_gdp_pct(base, gdp_path)
        dec_path = output_path.replace('.csv', '_pct_gdp.csv')
        dec.to_csv(dec_path)
        print(f"pct-of-GDP report saved to: {dec_path}")
    except Exception as e:
        print(f"Warning: Could not compute percentage GDP ratios - {e}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python main.py <data_csv> <dictionary_txt> <gdp_csv> <output_csv>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
