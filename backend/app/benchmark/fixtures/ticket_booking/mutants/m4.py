def book_tickets(available, requested, max_per_booking):
    if requested <= 0:
        return "invalid_quantity"
    if requested > available:
        return "sold_out"
    return available - requested
