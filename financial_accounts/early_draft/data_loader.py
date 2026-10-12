import pandas as pd

class DataLoader:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.df = None
        self.latest_data = None
        self.date_columns = ['date']

    def load_data(self):
        """Load and clean CSV data"""
        self.df = pd.read_csv(self.csv_path)

        # Convert ND values to NaN and clean numeric columns
        non_date_cols = [col for col in self.df.columns if col not in self.date_columns]
        self.df[non_date_cols] = self.df[non_date_cols].apply(pd.to_numeric, errors='coerce')

        # Remove entirely empty rows
        self.df = self.df.dropna(how='all', subset=non_date_cols)

        # Get latest quarter data
        self.latest_data = self.df.iloc[-1].to_dict()
        self.latest_date = self.latest_data['date']

    def get_value(self, series_id):
        """Get value for a series ID"""
        return self.latest_data.get(f"{series_id}.Q")
