import re

class HierarchyParser:
    def __init__(self, pdf_text):
        self.pdf_text = pdf_text
        self.hierarchy = {}
        self.top_level_assets = []
        self.total_liabilities_id = None
        self.total_assets_id = None

    def parse(self):
        """Parse PDF text to extract series hierarchy"""
        lines = self.pdf_text.split('\n')
        current_parent = None
        parent_stack = []

        for line in lines:
            # Skip empty lines and headers
            if not line.strip() or any(x in line.lower() for x in ["levels", "z.1", "billions", "202", "q", "(", "memo"]):
                continue

            # Extract series info
            match = re.match(r'^\s*(\d+)\s+([A-Z0-9]+\.[A-Z0-9]+)\s+(.*?)(?:\s+\d+)?$', line.strip())
            if not match:
                continue

            line_num = int(match.group(1))
            series_id = match.group(2)
            description = match.group(3).strip()

            # Determine hierarchy level
            if "total liabilities" in description.lower():
                self.total_liabilities_id = series_id
                current_parent = series_id
                parent_stack = [series_id]
                self.hierarchy[series_id] = {
                    'description': description,
                    'children': []
                }
            elif "total assets" in description.lower():
                self.total_assets_id = series_id
                current_parent = series_id
                parent_stack = [series_id]
                self.hierarchy[series_id] = {
                    'description': description,
                    'children': []
                }
                self.top_level_assets.append(series_id)
            elif current_parent:
                # Check if this is a sub-item
                if parent_stack and line_num > 1:
                    self.hierarchy[parent_stack[-1]]['children'].append(series_id)
                    self.hierarchy[series_id] = {
                        'description': description,
                        'children': []
                    }

                    # For assets, only track top-level holders
                    if self.total_assets_id and parent_stack[-1] == self.total_assets_id:
                        self.top_level_assets.append(series_id)
