def paginate_query(query, page: int = 1, per_page: int = 20, serialize_fn=None) -> dict:
    """Utility function to apply standardized offset-limit pagination to SQLAlchemy queries."""
    try:
        page = int(page) if page and str(page).isdigit() else 1
    except (ValueError, TypeError):
        page = 1
        
    try:
        per_page = int(per_page) if per_page and str(per_page).isdigit() else 20
    except (ValueError, TypeError):
        per_page = 20
        
    page = max(1, page)
    per_page = min(100, max(1, per_page))
    
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    
    serialized_items = []
    for item in items:
        if serialize_fn:
            serialized_items.append(serialize_fn(item))
        elif hasattr(item, 'to_dict'):
            serialized_items.append(item.to_dict())
        else:
            serialized_items.append(item)
            
    return {
        'items': serialized_items,
        'pagination': {
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1
        }
    }
