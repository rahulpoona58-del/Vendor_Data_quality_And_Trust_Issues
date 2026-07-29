from datetime import datetime
from src.infrastructure.database.models import CopilotMessage, Vendor, VendorDocument, SystemAuditLog, VendorComplianceStatus, InvestigationCase, db
from src.domain.services.semantic_search import SemanticSearchEngine
import logging

class CopilotService:
    """Retrieval-Augmented Generation (RAG) copilot resolving telemetry questions exclusively from project database entries."""
    
    @staticmethod
    def process_query(session_id: str, message: str) -> str:
        """Processes message via dynamic semantic retrieval and formats grounded answers with sources."""
        try:
            # 1. Save user query
            u_msg = CopilotMessage(session_id=session_id, sender='user', message=message)
            db.session.add(u_msg)
            db.session.commit()
            
            # 2. Retrieve context via semantic TF-IDF matcher (RAG phase)
            retrieval = SemanticSearchEngine.execute_semantic_search(message, threshold=0.03)
            hits = retrieval.get('results', []) + retrieval.get('similar_results', [])
            
            if not hits:
                response = (
                    "🤖 I checked our project records for your query, but could not identify any closely matching information.\n\n"
                    "**Guardrail Warning**: To prevent hallucination, I am restricted to answering questions strictly grounded in project database registries."
                )
            else:
                # 3. Build a structured fact response from retrieved entries
                response = f"### 🤖 Factual Copilot Response (Retrieval-Augmented)\n\n"
                
                # Deduplicate and group by type
                grouped_hits = {}
                for hit in hits:
                    htype = hit['type']
                    if htype not in grouped_hits:
                        grouped_hits[htype] = []
                    # Keep top 3 per type to avoid context clutter
                    if len(grouped_hits[htype]) < 3:
                        grouped_hits[htype].append(hit)
                
                # Format answers based on context
                for htype, items in grouped_hits.items():
                    response += f"#### 📂 {htype} Records Found:\n"
                    for item in items:
                        response += f"*   **{item['title']}** (Similarity Score: `{item['similarity_score']}`)\n"
                        response += f"    *   *Factual Details:* {item['description']}\n"
                        response += f"    *   *Source Referencing:* `[Database: {item['type']} Table | ID: {item['id']}]`\n\n"
                
                # Summary and recommendations
                response += "#### 💡 Suggested Action Items:\n"
                response += "*   Audit linked tax identifiers and GST records for profile matches.\n"
                response += "*   Inspect active audit trails for registry overrides."

            # 4. Save copilot answer
            c_msg = CopilotMessage(session_id=session_id, sender='copilot', message=response)
            db.session.add(c_msg)
            db.session.commit()
            
            return response
        except Exception as e:
            db.session.rollback()
            logging.error(f"Copilot RAG calculation failed: {str(e)}")
            return f"⚠️ Engine encountered RAG processing exception: {str(e)}"

    @staticmethod
    def get_history(session_id: str, limit: int = 20) -> list:
        """Retrieves chronological conversational logs for the active session."""
        try:
            msgs = CopilotMessage.query.filter_by(session_id=session_id)\
                                       .order_by(CopilotMessage.created_at.asc())\
                                       .limit(limit).all()
            return [m.to_dict() for m in msgs]
        except Exception as e:
            logging.error(f"Error retrieving chat history: {str(e)}")
            return []
