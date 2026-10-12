import pandas as pd

def process_repo_data(input_file_path):
    """
    Reads repo data with YYYYMMDD date format, processes it to find total
    collateral values, and outputs monthly, quarterly average, and
    end-of-quarter values to new CSV files.

    Args:
        input_file_path (str): The path to the input CSV file.
    """
    try:
        # Load the dataset from the specified CSV file
        df = pd.read_csv(input_file_path)

        # --- Data Cleaning and Preparation ---

        # Standardize column names for easier access
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

        # Convert the date column from YYYYMMDD integer format to a datetime object.
        date_column_name = df.columns[0]
        df[date_column_name] = pd.to_datetime(df[date_column_name], format='%Y%m%d')

        # Filter the DataFrame to include only rows where 'group_id' is 0,
        # as these represent the total collateral value.
        total_collateral_df = df[df['group_id'] == 0].copy()

        # Identify the name of the column containing the collateral values.
        collateral_column_name = [col for col in total_collateral_df.columns if 'collateral' in col][0]

        # Set the date column as the index to perform time-series resampling.
        total_collateral_df.set_index(date_column_name, inplace=True)

        # --- 1. Create CSV for Monthly Collateral Values ---
        # Resample the data by calendar month ('M').
        # Use .last() to get the last reported value for each month.
        # .dropna() removes any months that had no data.
        monthly_values = total_collateral_df[collateral_column_name].resample('M').last().dropna()

        monthly_output_df = monthly_values.reset_index()
        monthly_output_df.columns = ['month', 'collateral_value']

        # Format the date as YYYY-MM
        monthly_output_df['month'] = monthly_output_df['month'].dt.strftime('%Y-%m')

        monthly_output_file = 'monthly_collateral.csv'
        monthly_output_df.to_csv(monthly_output_file, index=False)
        print(f"Successfully created monthly collateral file: {monthly_output_file}")


        # --- 2. Calculate and Create CSV for Quarterly Averages ---
        # Resample the data by calendar quarter ('Q') and calculate the mean.
        quarterly_average = total_collateral_df[collateral_column_name].resample('Q').mean().dropna()

        quarterly_average_df = quarterly_average.reset_index()
        quarterly_average_df.columns = ['quarter', 'average_collateral_value']

        # Format the quarter as YYYY:Q#
        quarterly_average_df['quarter'] = quarterly_average_df['quarter'].apply(lambda d: f"{d.year}:Q{d.quarter}")

        quarterly_average_file = 'quarterly_average_collateral.csv'
        quarterly_average_df.to_csv(quarterly_average_file, index=False)
        print(f"Successfully created quarterly average collateral file: {quarterly_average_file}")


        # --- 3. Calculate and Create CSV for End-of-Quarter Values ---
        # Resample by quarter ('Q') and get the last recorded value.
        end_of_quarter_values = total_collateral_df[collateral_column_name].resample('Q').last().dropna()

        end_of_quarter_df = end_of_quarter_values.reset_index()
        end_of_quarter_df.columns = ['quarter', 'end_of_quarter_collateral_value']

        # Format the quarter as YYYY:Q#
        end_of_quarter_df['quarter'] = end_of_quarter_df['quarter'].apply(lambda d: f"{d.year}:Q{d.quarter}")

        end_of_quarter_file = 'end_of_quarter_collateral.csv'
        end_of_quarter_df.to_csv(end_of_quarter_file, index=False)
        print(f"Successfully created end-of-quarter collateral file: {end_of_quarter_file}")


    except FileNotFoundError:
        print(f"Error: The file '{input_file_path}' was not found.")
    except KeyError as e:
        print(f"Error: A required column was not found in the CSV: {e}")
        print("Please check the column names in your CSV file and adjust the script if necessary.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")



if __name__ == '__main__':
    # Set the path to the input CSV file here
    input_csv_file = 'repo_data.csv'
    process_repo_data(input_csv_file)

