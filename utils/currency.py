

def convert_currency(amount, currency):
    rates = {
        "USD": 1,
        "EUR": 0.92,
        "INR": 83
    }
    return amount * rates.get(currency, 1)


def format_currency(value, currency):
    symbols = {
        "USD": "$",
        "EUR": "€",
        "INR": "₹"
    }
    return f"{symbols.get(currency, '$')} {value:,.2f}"



def get_symbol(currency):
    symbols = {
        "USD": "$",
        "EUR": "€",
        "INR": "₹"
    }
    return symbols.get(currency, currency)

