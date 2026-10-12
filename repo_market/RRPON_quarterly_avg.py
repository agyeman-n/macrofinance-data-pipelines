import pandas as pd

def calculate_quarterly_average(input_csv_path, output_csv_path):
    """
    Reads daily overnight reverse repo data, calculates the quarterly average,
    and saves the result to a new CSV file.

    Args:
        input_csv_path (str): The file path for the input CSV.
        output_csv_path (str): The file path for the output CSV.
    """
    try:
        # Step 1: Read the CSV, parsing the first column as dates by its position (0).
        # This avoids errors if the 'DATE' header is missing or misspelled.
        df = pd.read_csv(input_csv_path, parse_dates=[0])

        # Step 2: Standardize column names to ensure the rest of the script works.
        # We rename the columns based on their expected positions.
        df.columns = ['DATE', 'RRPONTTLD']

        # Step 3: Handle non-numeric values in the repo column.
        # The FRED dataset uses '.' for missing data. We convert the column
        # to a numeric type, and any values that can't be converted
        # (like '.') will become NaN (Not a Number).
        df['RRPONTTLD'] = pd.to_numeric(df['RRPONTTLD'], errors='coerce')

        # Step 4: Drop days with missing data.
        # FRED marks non-reporting days (weekends, holidays) with '.', so those
        # days carry no information. Counting them as zero would pull the
        # quarterly averages down. Days with genuinely zero usage are reported
        # as 0 and are kept.
        df = df.dropna(subset=['RRPONTTLD'])

        # Step 5: Create a new column to represent the quarter in 'YYYY:Q#' format.
        # - df['DATE'].dt.year gives the year (e.g., 2023).
        # - df['DATE'].dt.quarter gives the quarter number (1, 2, 3, or 4).
        # We combine these into the desired string format.
        df['QUARTER'] = df['DATE'].dt.year.astype(str) + ':Q' + df['DATE'].dt.quarter.astype(str)

        # Step 6: Group the DataFrame by the new 'QUARTER' column and calculate the mean.
        # - groupby('QUARTER') collects all rows for each unique quarter.
        # - ['RRPONTTLD'] selects the column we want to aggregate.
        # - mean() calculates the average for that column within each group.
        # - reset_index() converts the grouped output back into a DataFrame.
        quarterly_avg = df.groupby('QUARTER')['RRPONTTLD'].mean().reset_index()

        # Step 7: Rename the columns for clarity in the output file.
        quarterly_avg.rename(columns={'RRPONTTLD': 'AVERAGE_RRPONTTLD'}, inplace=True)

        # Step 8: Save the resulting DataFrame to a new CSV file.
        # index=False prevents pandas from writing the DataFrame index as a column.
        quarterly_avg.to_csv(output_csv_path, index=False)

        print(f"Successfully created quarterly average file at: {output_csv_path}")

    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Main execution ---
if __name__ == "__main__":
    # Define the input and output file names.
    # Assumes 'RRPONTTLD.csv' is in the same directory as the script.
    input_file = 'RRPONTTLD.csv'
    output_file = 'rrpon_qaverage.csv'

    # Call the function to perform the calculation and save the file.
    calculate_quarterly_average(input_file, output_file)
