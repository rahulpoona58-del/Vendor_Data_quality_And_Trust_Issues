from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.infrastructure.database.models import Vendor, VendorDocument, SystemAuditLog, VendorComplianceStatus, InvestigationCase
import numpy as np
import logging

class SemanticSearchEngine:
    """Calculates TF-IDF vector similarity across all system entities to return ranked semantic matches."""
    
    @staticmethod
    def execute_semantic_search(query_text: str, result_type: str = 'All', threshold: float = 0.02) -> dict:
        """Executes similarity ranking across Vendors, Documents, Audits, Compliance, and Investigations."""
        if not query_text:
            return {'success': True, 'results': [], 'similar_results': []}
            
        try:
            # 1. Fetch records
            vendors = Vendor.query.all()
            documents = VendorDocument.query.all()
            audit_logs = SystemAuditLog.query.all()
            compliance_profiles = VendorComplianceStatus.query.all()
            cases = InvestigationCase.query.all()

            corpus = []
            metadata = []

            # 2. Add Vendor texts
            for v in vendors:
                text = f"Vendor profile: Name {v.name} | Category {v.category} | Status {v.status} | Address {v.address} | Email {v.email}"
                corpus.append(text)
                metadata.append({
                    'type': 'Vendor',
                    'id': v.id,
                    'title': v.name,
                    'description': f"Category: {v.category} | Status: {v.status} | Trust Score: {v.trust_score}",
                    'raw_object': v.to_dict()
                })

            # 3. Add Document texts
            for d in documents:
                text = f"Document: Name {d.name} | Type {d.document_type} | Verification {d.verification_status} | Vendor ID {d.vendor_id}"
                corpus.append(text)
                metadata.append({
                    'type': 'Document',
                    'id': d.id,
                    'title': d.name,
                    'description': f"Type: {d.document_type} | Status: {d.verification_status} (Vendor Ref: #{d.vendor_id})",
                    'raw_object': d.to_dict()
                })

            # 4. Add Audit log texts
            for log in audit_logs:
                text = f"Audit log: Action {log.action_type} | Module {log.module_name} | User {log.performed_by} | Reason {log.reason}"
                corpus.append(text)
                metadata.append({
                    'type': 'Audit Log',
                    'id': log.id,
                    'title': log.action_type,
                    'description': f"Module: {log.module_name} by {log.performed_by} | Reason: {log.reason}",
                    'raw_object': log.to_dict()
                })

            # 5. Add Compliance texts
            for comp in compliance_profiles:
                v_name = comp.vendor.name if comp.vendor else f"Vendor #{comp.vendor_id}"
                text = f"Compliance: Vendor {v_name} | Status {comp.approval_status} | Auditor {comp.audited_by} | Score {comp.compliance_score}"
                corpus.append(text)
                metadata.append({
                    'type': 'Compliance',
                    'id': comp.id,
                    'title': f"Compliance Status - {v_name}",
                    'description': f"Score: {comp.compliance_score}% | Status: {comp.approval_status}",
                    'raw_object': comp.to_dict()
                })

            # 6. Add Investigation texts
            for c in cases:
                notes_text = " ".join([n.get('text', '') for n in (c.evidence_notes or [])])
                text = f"Investigation Case: Number {c.case_number} | Priority {c.priority} | Status {c.status} | Notes {notes_text}"
                corpus.append(text)
                metadata.append({
                    'type': 'Investigation',
                    'id': c.id,
                    'title': c.case_number,
                    'description': f"Status: {c.status} | Priority: {c.priority} | Notes: {c.resolution_details or 'Under audit'}",
                    'raw_object': c.to_dict()
                })

            if not corpus:
                return {'success': True, 'results': [], 'similar_results': []}

            # 7. Compute TF-IDF Cosine Similarity
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(corpus)
            query_vector = vectorizer.transform([query_text])
            
            similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
            
            # Sort descending
            ranked_indices = np.argsort(similarities)[::-1]
            
            results = []
            similar_results = []
            
            for idx in ranked_indices:
                score = float(similarities[idx])
                if score < threshold:
                    continue
                    
                item = metadata[idx]
                item['similarity_score'] = round(score, 3)
                
                # Filter by result_type if not All
                if result_type != 'All' and item['type'] != result_type:
                    continue
                    
                # Separate into primary hits vs alternative similarities
                if score > 0.15:
                    results.append(item)
                elif score > 0.04:
                    similar_results.append(item)

            return {
                'success': True,
                'results': results[:25],
                'similar_results': similar_results[:10]
            }
        except Exception as e:
            logging.error(f"Semantic search processing failed: {str(e)}")
            return {'success': False, 'message': str(e)}
