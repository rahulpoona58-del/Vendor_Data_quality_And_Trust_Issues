import re
from datetime import datetime
from sqlalchemy import or_
from src.infrastructure.database.models import Vendor, VendorDocument, FraudCheck, VendorComplianceStatus, db
import logging

class SmartSearchEngine:
    """Natural Language & Multi-Field Search Engine compiling dynamic vendor records."""
    
    @staticmethod
    def parse_query(query: str) -> dict:
        """Parses query string for NLP filters and regex syntax patterns."""
        filters = {}
        query = query.lower().strip()
        
        # 1. Pattern: "trust score below/under/less than 60"
        m_trust_below = re.search(r"trust\s+score\s+(below|less\s+than|under)\s+(\d+)", query)
        if m_trust_below:
            filters['trust_below'] = float(m_trust_below.group(2))
            
        # 2. Pattern: "trust score above/over/greater than 60"
        m_trust_above = re.search(r"trust\s+score\s+(above|greater\s+than|over)\s+(\d+)", query)
        if m_trust_above:
            filters['trust_above'] = float(m_trust_above.group(2))
            
        # 3. Pattern: "duplicate vendors"
        if "duplicate" in query:
            filters['only_duplicates'] = True
            
        # 4. Pattern: "from Delhi" or "in Mumbai"
        m_city = re.search(r"(from|in|at)\s+([a-zA-Z\s]+)", query)
        if m_city:
            city = m_city.group(2).strip()
            if city not in {'trust', 'compliance', 'score', 'vendor'}: # filter out query stop words
                filters['city'] = city
                
        # 5. Pattern: "expired GST" or "GST expired"
        if "expired gst" in query or "gst expired" in query:
            filters['expired_gst'] = True
            
        # 6. Pattern: "expired PAN" or "PAN expired"
        if "expired pan" in query or "pan expired" in query:
            filters['expired_pan'] = True

        return filters

    @staticmethod
    def execute_search(query: str, page: int = 1, limit: int = 10, sort_by: str = None, order: str = 'desc', category: str = None, trust_level: str = None) -> dict:
        """Runs the parsed filters and standard keyword searches on vendor tables."""
        try:
            filters = SmartSearchEngine.parse_query(query)
            db_query = Vendor.query
            
            # Apply dynamic NLP filters
            if 'trust_below' in filters:
                db_query = db_query.filter(Vendor.trust_score < filters['trust_below'])
            if 'trust_above' in filters:
                db_query = db_query.filter(Vendor.trust_score > filters['trust_above'])
                
            if 'city' in filters:
                city_safe = str(filters['city']).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                db_query = db_query.filter(Vendor.address.ilike(f"%{city_safe}%"))
                
            if filters.get('only_duplicates'):
                # Optimized subquery using SQL ilike filter and column projection
                dup_tuples = db.session.query(FraudCheck.vendor_id).filter(FraudCheck.supporting_evidence.ilike('%duplicate%')).all()
                dup_vendor_ids = [t[0] for t in dup_tuples]
                db_query = db_query.filter(Vendor.id.in_(dup_vendor_ids))
                
            if filters.get('expired_gst') or filters.get('expired_pan'):
                now = datetime.utcnow()
                doc_type = 'GST Certificate' if filters.get('expired_gst') else 'PAN Card'
                exp_tuples = db.session.query(VendorDocument.vendor_id).filter(
                    VendorDocument.document_type == doc_type,
                    VendorDocument.expiry_date < now,
                    VendorDocument.is_deleted == False
                ).all()
                expired_vendor_ids = [t[0] for t in exp_tuples]
                db_query = db_query.filter(Vendor.id.in_(expired_vendor_ids))

            # Apply standard keyword search fallback if no NLP filters found
            if not filters and query:
                # Scans vendor name, email, phone, address, and document tags with column projection
                doc_tuples = db.session.query(VendorDocument.vendor_id).filter(
                    VendorDocument.is_deleted == False,
                    ((VendorDocument.name.ilike(f"%{query}%")) |
                     (VendorDocument.document_type.ilike(f"%{query}%")))
                ).all()
                doc_vendor_ids = [t[0] for t in doc_tuples]
                
                db_query = db_query.filter(
                    or_(
                        Vendor.name.ilike(f"%{query}%"),
                        Vendor.email.ilike(f"%{query}%"),
                        Vendor.phone.ilike(f"%{query}%"),
                        Vendor.address.ilike(f"%{query}%"),
                        Vendor.id.in_(doc_vendor_ids)
                    )
                )

            # Apply sidebar filters
            if category and category != 'All':
                db_query = db_query.filter(Vendor.category == category)
            if trust_level and trust_level != 'All':
                db_query = db_query.filter(Vendor.trust_level == trust_level)

            # Apply sorting
            if sort_by:
                col = getattr(Vendor, sort_by, None)
                if col:
                    db_query = db_query.order_by(col.desc() if order == 'desc' else col.asc())
            else:
                db_query = db_query.order_by(Vendor.trust_score.desc())

            # Apply pagination
            total = db_query.count()
            paginated = db_query.paginate(page=page, per_page=limit, error_out=False)
            
            results = []
            for v in paginated.items:
                results.append({
                    'id': v.id,
                    'name': v.vendor_name,
                    'trust_score': v.trust_score,
                    'trust_level': v.trust_level,
                    'category': v.category,
                    'status': v.status,
                    'quality_rating': v.quality_rating,
                    'email': v.email,
                    'phone': v.phone,
                    'address': v.address
                })
                
            return {
                'success': True,
                'total': total,
                'page': page,
                'limit': limit,
                'results': results
            }
        except Exception as e:
            logging.error(f"Smart Search execution failed: {str(e)}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def get_suggestions(prefix: str) -> list:
        """Fetches autocomplete suggestion templates for search prefix matching."""
        suggestions = []
        prefix = prefix.lower().strip()
        
        # Default NLP query templates
        templates = [
            "Show vendors with trust score below 60",
            "Show duplicate vendors",
            "Show vendors from Delhi",
            "Show vendors with expired GST"
        ]
        
        for t in templates:
            if prefix in t.lower():
                suggestions.append({'type': 'template', 'text': t})
                
        # Matching vendor profiles
        try:
            vendors = Vendor.query.filter(Vendor.name.ilike(f"%{prefix}%")).limit(5).all()
            for v in vendors:
                suggestions.append({'type': 'vendor', 'text': v.vendor_name, 'id': v.id})
        except Exception:
            pass
            
        return suggestions[:6]
