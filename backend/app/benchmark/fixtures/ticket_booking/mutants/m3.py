def book_tickets(available, requested, max_per_booking):
    if requested <= 0:
        return "invalid_quantity"
    if requested > max_per_booking:
        return "exceeds_limit"
    if requested >= available:
        return "sold_out"
    return available - requested
