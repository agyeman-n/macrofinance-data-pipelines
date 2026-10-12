#!/usr/bin/env python3
"""
Treasury Securities Data Reconciliation Script

This script performs a comprehensive reconciliation of U.S. Treasury securities
outstanding values by comparing:
1. Bottom-up calculation from CRSP US Treasury database (via WRDS)
2. Top-down official data: the Federal Reserve Bank of Dallas series
   "Market Value of Marketable Treasury Debt" (FRED: MVMTD027MNFRBDAL)

The script calculates quarter-end and quarterly-average market values and
generates reconciliation reports.
"""

import pandas as pd
import numpy as np
import wrds
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, date
import getpass
import warnings
import sys

# FRED series used as the top-down benchmark. It measures the market value of
# all marketable Treasury debt (monthly, end of month, billions of dollars),
# which is the same concept as summing CRSP market values across securities.
FRED_SERIES = 'MVMTD027MNFRBDAL'
FRED_CSV_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'


# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Set up plotting style
try:
    plt.style.use('seaborn-v0_8')
except:
    plt.style.use('default')
sns.set_palette("husl")

def connect_to_wrds():
    """
    Connect to WRDS database with user credentials.
    
    Returns:
        wrds.Connection: Authenticated WRDS connection object
    """
    print("=== WRDS Database Connection ===")
    print("Please enter your WRDS credentials:")
    
    username = input("WRDS Username: ")
    password = getpass.getpass("WRDS Password: ")
    
    try:
        print("Connecting to WRDS...")
        db = wrds.Connection(wrds_username=username, wrds_password=password)
        print("✓ Successfully connected to WRDS!")
        return db
    except Exception as e:
        print(f"✗ Failed to connect to WRDS: {e}")
        sys.exit(1)

def get_crsp_treasury_data(db, start_date='1961-01-01', end_date=None, debug=False):
    """
    Query CRSP Treasury data and calculate quarterly market values.
    
    Args:
        db (wrds.Connection): WRDS database connection
        start_date (str): Start date in YYYY-MM-DD format (default: 1961-01-01)
        end_date (str): End date in YYYY-MM-DD format (None for today)
        debug (bool): Enable detailed debugging output
    
    Returns:
        pd.DataFrame: Quarterly aggregated market values from CRSP
    """
    if end_date is None:
        end_date = date.today().strftime('%Y-%m-%d')
    
    print(f"\n=== Querying CRSP Treasury Data ({start_date} to {end_date}) ===")
    
    # SQL query to get CRSP Treasury daily data
    query = f"""
    SELECT 
        caldt as date,
        tdtotout as amount_outstanding,
        tdbid as bid_price,
        tdask as ask_price,
        tdaccint as accrued_interest
    FROM crsp.tfz_dly
    WHERE caldt >= '{start_date}'
      AND caldt <= '{end_date}'
      AND tdtotout IS NOT NULL
      AND tdbid IS NOT NULL
      AND tdask IS NOT NULL
      AND tdaccint IS NOT NULL
      AND tdtotout > 0
      AND tdbid > 0
      AND tdask > 0
    ORDER BY caldt
    """
    
    try:
        print("Executing CRSP query...")
        crsp_data = db.raw_sql(query)
        print(f"✓ Retrieved {len(crsp_data):,} daily observations from CRSP")
        
        if crsp_data.empty:
            print("✗ No data retrieved from CRSP. Please check your query parameters.")
            return pd.DataFrame()
        
        # Convert date column to datetime
        crsp_data['date'] = pd.to_datetime(crsp_data['date'])
        
        # Calculate market values
        print("Calculating market values...")
        
        # Price is average of bid and ask (both quoted per $100 of face value)
        crsp_data['avg_price'] = (crsp_data['bid_price'] + crsp_data['ask_price']) / 2
        
        # Market value = face outstanding * (clean price + accrued interest) / 100
        # tdtotout is face value outstanding in millions of dollars (CRSP
        # US Treasury Database Guide), so convert to dollars first.
        crsp_data['market_value'] = (crsp_data['amount_outstanding'] * 1e6 / 100) * \
                                  (crsp_data['avg_price'] + crsp_data['accrued_interest'])
        
        # Step 1: total across all securities on each day
        print("Aggregating to daily totals across securities...")
        daily = crsp_data.groupby('date').agg(
            daily_market_value=('market_value', 'sum'),
            daily_face_value=('amount_outstanding', 'sum'),
            securities=('market_value', 'count'),
        ).reset_index()
        
        # Step 2: aggregate daily totals to quarters. The quarter-end value
        # (last trading day) matches the end-of-month FRED benchmark; the
        # quarterly average matches series built from quarterly averages.
        print("Aggregating daily totals to quarters...")
        daily['quarter'] = daily['date'].dt.to_period('Q')
        quarterly_crsp = daily.sort_values('date').groupby('quarter').agg(
            quarter_end_market_value=('daily_market_value', 'last'),
            avg_market_value=('daily_market_value', 'mean'),
            quarter_end_face_value_mil=('daily_face_value', 'last'),
            daily_obs=('date', 'count'),
            avg_securities=('securities', 'mean'),
        )
        
        # Convert to billions
        quarterly_crsp['crsp_total_billions'] = quarterly_crsp['quarter_end_market_value'] / 1e9
        quarterly_crsp['crsp_avg_billions'] = quarterly_crsp['avg_market_value'] / 1e9
        quarterly_crsp['crsp_face_billions'] = quarterly_crsp['quarter_end_face_value_mil'] / 1e3
        
        # Use the calendar quarter-end date as the merge key
        quarterly_crsp = quarterly_crsp.reset_index()
        quarterly_crsp['quarter_end'] = quarterly_crsp['quarter'].dt.end_time.dt.date
        quarterly_crsp['date'] = pd.to_datetime(quarterly_crsp['quarter_end'])
        
        print(f"✓ Calculated quarterly totals for {len(quarterly_crsp)} quarters")
        print(f"   Date range: {quarterly_crsp['quarter_end'].min()} to {quarterly_crsp['quarter_end'].max()}")
        print(f"   Average quarter-end market value: ${quarterly_crsp['crsp_total_billions'].mean():.1f}B")
        
        if debug:
            print("\n🔍 DEBUG: Detailed CRSP Calculation Summary")
            print(f"   Total daily observations: {len(crsp_data):,}")
            print(f"   Unique securities per day (avg): {daily['securities'].mean():.0f}")
            print(f"   Average amount outstanding per security: ${crsp_data['amount_outstanding'].mean() * 1e6:,.0f}")
            print(f"   Average market value per security: ${crsp_data['market_value'].mean() / 1e9:.3f}B")
            print(f"   Price range: ${crsp_data['avg_price'].min():.2f} - ${crsp_data['avg_price'].max():.2f}")
            print(f"   Accrued interest range: ${crsp_data['accrued_interest'].min():.2f} - ${crsp_data['accrued_interest'].max():.2f}")
        
        return quarterly_crsp[['date', 'crsp_total_billions', 'crsp_avg_billions',
                               'crsp_face_billions', 'daily_obs']]
        
    except Exception as e:
        print(f"✗ Error querying CRSP data: {e}")
        return pd.DataFrame()

def get_fred_treasury_data(start_date='1961-01-01', end_date=None, series=FRED_SERIES):
    """
    Download the market value of marketable Treasury debt from FRED.
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format (default: 1961-01-01)
        end_date (str): End date in YYYY-MM-DD format (None for today)
        series (str): FRED series ID (default: MVMTD027MNFRBDAL, billions of dollars)
    
    Returns:
        pd.DataFrame: Quarter-end Treasury market values from FRED
    """
    if end_date is None:
        end_date = date.today().strftime('%Y-%m-%d')
    
    print(f"\n=== Downloading FRED Treasury Data ({start_date} to {end_date}) ===")
    
    try:
        print(f"Downloading {series} series from FRED...")
        
        # Read FRED's CSV endpoint directly ('.' marks missing values)
        fred_data = pd.read_csv(FRED_CSV_URL.format(series=series), na_values='.')
        fred_data.columns = ['date', 'fred_total_billions']
        fred_data['date'] = pd.to_datetime(fred_data['date'])
        fred_data = fred_data[(fred_data['date'] >= start_date) & (fred_data['date'] <= end_date)]
        fred_data = fred_data.dropna(subset=['fred_total_billions'])
        
        if fred_data.empty:
            print("✗ No data retrieved from FRED")
            return pd.DataFrame()
        
        print(f"✓ Retrieved {len(fred_data):,} observations from FRED")
        
        # Monthly end-of-month values: keep the last month of each quarter
        fred_data['quarter'] = fred_data['date'].dt.to_period('Q')
        fred_quarterly = fred_data.sort_values('date').groupby('quarter').last().reset_index()
        fred_quarterly['date'] = pd.to_datetime(fred_quarterly['quarter'].dt.end_time.dt.date)
        
        print(f"✓ Processed to {len(fred_quarterly)} quarterly observations")
        print(f"   Date range: {fred_quarterly['date'].min().date()} to {fred_quarterly['date'].max().date()}")
        print(f"   Average quarter-end value: ${fred_quarterly['fred_total_billions'].mean():.1f}B")
        
        return fred_quarterly[['date', 'fred_total_billions']]
        
    except Exception as e:
        print(f"✗ Error downloading FRED data: {e}")
        return pd.DataFrame()

def reconcile_data(crsp_data, fred_data):
    """
    Merge and reconcile CRSP and FRED data.
    
    Args:
        crsp_data (pd.DataFrame): Quarterly CRSP data
        fred_data (pd.DataFrame): Quarterly FRED data
    
    Returns:
        pd.DataFrame: Merged and reconciled dataset
    """
    print("\n=== Reconciling CRSP and FRED Data ===")
    
    if crsp_data.empty or fred_data.empty:
        print("✗ Cannot reconcile: one or both datasets are empty")
        return pd.DataFrame()
    
    # Ensure both datasets have the same date format for merging
    crsp_data['date_str'] = crsp_data['date'].dt.strftime('%Y-%m-%d')
    fred_data['date_str'] = fred_data['date'].dt.strftime('%Y-%m-%d')
    
    # Merge datasets on date strings to avoid timezone issues
    merged_data = pd.merge(crsp_data, fred_data, on='date_str', how='outer', suffixes=('_crsp', '_fred'))
    
    # Use the CRSP date column as the primary date
    merged_data['date'] = merged_data['date_crsp'].fillna(merged_data['date_fred'])
    
    # Sort by date
    merged_data = merged_data.sort_values('date').reset_index(drop=True)
    
    # Clean up temporary columns
    merged_data = merged_data.drop(['date_str', 'date_crsp', 'date_fred'], axis=1, errors='ignore')
    
    # Fill missing values with NaN for proper calculation
    merged_data['crsp_total_billions'] = merged_data['crsp_total_billions'].fillna(np.nan)
    merged_data['fred_total_billions'] = merged_data['fred_total_billions'].fillna(np.nan)
    
    # Calculate discrepancy (CRSP - FRED) only where both values exist
    merged_data['discrepancy_billions'] = np.where(
        merged_data['crsp_total_billions'].notna() & merged_data['fred_total_billions'].notna(),
        merged_data['crsp_total_billions'] - merged_data['fred_total_billions'],
        np.nan
    )
    
    # Calculate percentage difference only where both values exist
    merged_data['discrepancy_pct'] = np.where(
        merged_data['crsp_total_billions'].notna() & merged_data['fred_total_billions'].notna() & (merged_data['fred_total_billions'] != 0),
        (merged_data['discrepancy_billions'] / merged_data['fred_total_billions']) * 100,
        np.nan
    )
    
    # Add summary statistics
    print(f"✓ Merged dataset contains {len(merged_data)} quarters")
    print(f"   Common date range: {merged_data['date'].min().date()} to {merged_data['date'].max().date()}")
    
    # Calculate summary statistics for non-null observations
    valid_data = merged_data.dropna(subset=['crsp_total_billions', 'fred_total_billions'])
    
    if not valid_data.empty:
        print(f"\n📊 Reconciliation Summary ({len(valid_data)} complete observations):")
        print(f"   Average CRSP Total: ${valid_data['crsp_total_billions'].mean():.1f}B")
        print(f"   Average FRED Total: ${valid_data['fred_total_billions'].mean():.1f}B")
        print(f"   Average Discrepancy: ${valid_data['discrepancy_billions'].mean():.1f}B ({valid_data['discrepancy_pct'].mean():.2f}%)")
        print(f"   Max Discrepancy: ${valid_data['discrepancy_billions'].abs().max():.1f}B")
        print(f"   Correlation: {valid_data['crsp_total_billions'].corr(valid_data['fred_total_billions']):.4f}")
    
    return merged_data

def save_results(reconciled_data, csv_filename='treasury_reconciliation.csv'):
    """
    Save reconciled data to CSV file.
    
    Args:
        reconciled_data (pd.DataFrame): Reconciled dataset
        csv_filename (str): Output CSV filename
    """
    print(f"\n=== Saving Results to {csv_filename} ===")
    
    try:
        # Prepare data for export
        export_data = reconciled_data.copy()
        export_data['date'] = export_data['date'].dt.strftime('%Y-%m-%d')
        
        # Round numerical columns with different precision
        for col in export_data.columns:
            if col in ['crsp_avg_billions']:
                export_data[col] = export_data[col].round(6)  # More precision for small averages
            elif col in ['crsp_total_billions', 'crsp_face_billions', 'fred_total_billions', 'discrepancy_billions', 'discrepancy_pct']:
                export_data[col] = export_data[col].round(3)
            elif col in ['daily_obs', 'unique_securities']:
                export_data[col] = export_data[col].round(0)  # No decimals for counts
        
        # Reorder columns to put date first
        date_col = export_data.pop('date')
        export_data.insert(0, 'date', date_col)
        
        # Save to CSV
        export_data.to_csv(csv_filename, index=False)
        print(f"✓ Data saved to {csv_filename}")
        print(f"   Columns: {list(export_data.columns)}")
        print(f"   Rows: {len(export_data)}")
        
    except Exception as e:
        print(f"✗ Error saving CSV: {e}")

def create_visualization(reconciled_data, plot_filename='treasury_reconciliation_plot.png'):
    """
    Create and save visualization of reconciled data.
    
    Args:
        reconciled_data (pd.DataFrame): Reconciled dataset
        plot_filename (str): Output plot filename
    """
    print(f"\n=== Creating Visualization: {plot_filename} ===")
    
    try:
        # Filter data with both CRSP and FRED values
        plot_data = reconciled_data.dropna(subset=['crsp_total_billions', 'fred_total_billions'])
        
        if plot_data.empty:
            print("✗ No data available for plotting")
            return
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))
        
        # Main comparison plot
        ax1.plot(plot_data['date'], plot_data['crsp_total_billions'], 
                label='CRSP, quarter-end market value (bottom-up)', linewidth=2, marker='o', markersize=4)
        ax1.plot(plot_data['date'], plot_data['fred_total_billions'], 
                label='Dallas Fed market value of marketable debt (FRED)', linewidth=2, marker='s', markersize=4)
        
        ax1.set_title('Market Value of Marketable U.S. Treasury Debt: CRSP vs. Dallas Fed', 
                     fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('Total Outstanding Value (Billions USD)', fontsize=12)
        ax1.legend(fontsize=11, loc='upper center', bbox_to_anchor=(0.5, 0.98), frameon=True, fancybox=True, shadow=True)
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        
        # Discrepancy plot
        ax2.plot(plot_data['date'], plot_data['discrepancy_billions'], 
                color='red', linewidth=2, marker='d', markersize=4)
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax2.set_title('Discrepancy (CRSP - FRED)', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Discrepancy (Billions USD)', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
        
        # Add summary statistics text box
        stats_text = f"""Summary Statistics ({len(plot_data)} quarters):
Avg CRSP: ${plot_data['crsp_total_billions'].mean():.1f}B
Avg FRED: ${plot_data['fred_total_billions'].mean():.1f}B
Avg Discrepancy: ${plot_data['discrepancy_billions'].mean():.1f}B
Correlation: {plot_data['crsp_total_billions'].corr(plot_data['fred_total_billions']):.4f}"""
        
        ax1.text(0.02, 0.85, stats_text, transform=ax1.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9))
        
        # Adjust layout and save
        plt.tight_layout(pad=2.0)
        plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Visualization saved to {plot_filename}")
        print(f"   Plot includes {len(plot_data)} quarterly observations")
        
    except Exception as e:
        print(f"✗ Error creating visualization: {e}")

def main():
    """
    Main execution function that orchestrates the entire reconciliation process.
    """
    print("🏛️  U.S. Treasury Securities Data Reconciliation")
    print("=" * 60)
    
    # Step 1: Connect to WRDS
    db = connect_to_wrds()
    
    try:
        # Step 2: Get CRSP data (going back to 1961)
        crsp_data = get_crsp_treasury_data(db, start_date='1961-01-01', debug=True)
        
        # Step 3: Get FRED data (going back to 1961)
        fred_data = get_fred_treasury_data(start_date='1961-01-01')
        
        # Step 4: Reconcile data
        reconciled_data = reconcile_data(crsp_data, fred_data)
        
        if not reconciled_data.empty:
            # Step 5: Save results
            save_results(reconciled_data)
            
            # Step 6: Create visualization
            create_visualization(reconciled_data)
            
            print(f"\n🎉 Reconciliation Complete!")
            print(f"📁 Output files:")
            print(f"   - treasury_reconciliation.csv")
            print(f"   - treasury_reconciliation_plot.png")
        else:
            print("✗ Reconciliation failed: no data to process")
    
    finally:
        # Clean up database connection
        if 'db' in locals():
            db.close()
            print("\n🔌 WRDS connection closed")

if __name__ == "__main__":
    main()