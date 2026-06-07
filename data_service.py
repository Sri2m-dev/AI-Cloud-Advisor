from views.cto_dashboard import load_cost_data
from core.data_processor import process_cost_data

def get_processed_data(currency):
    df = load_cost_data()
    return process_cost_data(df, currency)

