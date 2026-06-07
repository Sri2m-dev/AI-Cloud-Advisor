def format_inr(amount):
    """Format a number as INR currency with commas and no decimals if integer."""
    try:
        amount = float(amount)
        if amount.is_integer():
            return f"₹{int(amount):,}"
        else:
            return f"₹{amount:,.2f}"
    except Exception:
        return "₹0"

