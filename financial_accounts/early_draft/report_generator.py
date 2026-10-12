class ReportGenerator:
    def __init__(self, data_loader, hierarchy_parser):
        self.data_loader = data_loader
        self.hierarchy = hierarchy_parser.hierarchy
        self.top_level_assets = hierarchy_parser.top_level_assets
        self.total_liabilities_id = hierarchy_parser.total_liabilities_id
        self.total_assets_id = hierarchy_parser.total_assets_id

    def generate_report(self):
        """Generate comprehensive Treasury report"""
        report = []

        # Check if we found the required IDs
        if not self.total_liabilities_id:
            return "Error: Could not identify Total Liabilities in the PDF structure"
        if not self.total_assets_id:
            return "Error: Could not identify Total Assets in the PDF structure"

        # Total liabilities
        total_liab = self.data_loader.get_value(self.total_liabilities_id)
        report.append(f"The total number of treasuries is {total_liab:,.0f}\n")

        # Liabilities breakdown
        report.append("Breakdown of Liabilities:")
        for child_id in self.hierarchy.get(self.total_liabilities_id, {}).get('children', []):
            child_desc = self.hierarchy[child_id]['description']
            value = self.data_loader.get_value(child_id) or 0
            report.append(f"  {child_desc}: {value:,.0f}")
        report.append("")

        # Total assets
        total_assets = self.data_loader.get_value(self.total_assets_id)

        # Assets breakdown
        report.append("Breakdown of Assets by Holder:")
        asset_sum = 0
        for asset_id in self.top_level_assets:
            if asset_id == self.total_assets_id:
                continue  # Skip total assets itself

            desc = self.hierarchy[asset_id]['description']
            value = self.data_loader.get_value(asset_id) or 0
            asset_sum += value
            report.append(f"  {desc}: {value:,.0f}")

        # Sanity checks
        report.append("\nSanity Checks:")
        # Liabilities check
        liab_children = self.hierarchy.get(self.total_liabilities_id, {}).get('children', [])
        liab_children_sum = sum(self.data_loader.get_value(child_id) or 0
                                for child_id in liab_children)
        report.append(f"  Total Liabilities vs Components: {total_liab:,.0f} vs {liab_children_sum:,.0f} → "
                      f"{'Match' if abs(total_liab - liab_children_sum) < 1 else 'Mismatch'}")

        # Assets check
        report.append(f"  Total Assets vs Holder Sum: {total_assets:,.0f} vs {asset_sum:,.0f} → "
                      f"{'Match' if abs(total_assets - asset_sum) < 1 else 'Mismatch'}")

        return "\n".join(report)
