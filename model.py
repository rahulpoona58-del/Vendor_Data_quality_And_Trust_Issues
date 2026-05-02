import pandas as pd
from trust_score import calculate_trust_score, get_trust_level
import matplotlib.pyplot as plt

# Load dataset
df = pd.read_csv("vendors_20_columns.csv")

# Clean data
df.fillna(0, inplace=True)

# Add trust score
df['trust_score'] = df.apply(calculate_trust_score, axis=1)
df['trust_level'] = df['trust_score'].apply(get_trust_level)


# ✅ REQUIRED FUNCTION
def get_vendor(vendor_id):
    vendor = df[df['vendor_id'] == vendor_id]
    
    if vendor.empty:
        return None
    
    return vendor.to_dict(orient='records')[0]


# ✅ DASHBOARD
def get_all_vendors():
    return df.to_dict(orient='records')


# ✅ TOP VENDORS
def get_top_vendors(n=5):
    return df.sort_values(by='trust_score', ascending=False).head(n).to_dict(orient='records')


# ✅ CHART
def generate_chart():
    df['trust_score'].hist()
    plt.title("Trust Score Distribution")
    plt.savefig("static/chart.png")
    plt.close()