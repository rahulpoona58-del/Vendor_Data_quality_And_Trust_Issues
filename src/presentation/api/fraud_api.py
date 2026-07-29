from flask import Blueprint, request, jsonify
from src.domain.services.fraud_engine import FraudEngine
from src.infrastructure.database.models import FraudCheck
from src.infrastructure.security.decorators import login_required, role_required, get_current_user
import logging

fraud_api = Blueprint('fraud_api', __name__)

@fraud_api.route('/api/v2/vendors/<int:vendor_id>/fraud/scan', methods=['POST'])
@login_required
@role_required(['Admin', 'Data Steward', 'Manager', 'Auditor'])
def trigger_fraud_scan(vendor_id):
    """API endpoint to execute a comprehensive fraud scan on a vendor profile."""
    result = FraudEngine.execute_scan(vendor_id)
    if not result['success']:
        return jsonify(result), 400
    return jsonify(result), 200

@fraud_api.route('/api/v2/vendors/<int:vendor_id>/fraud/alerts', methods=['GET'])
@login_required
def get_vendor_fraud_alerts(vendor_id):
    """API endpoint to retrieve fraud check logs for a specific vendor."""
    alert = FraudCheck.query.filter_by(vendor_id=vendor_id).first()
    if not alert:
        return jsonify({'success': False, 'message': 'No fraud scans recorded for this vendor'}), 404
        
    return jsonify({'success': True, 'fraud_check': alert.to_dict()})

@fraud_api.route('/api/v2/fraud/alerts/<int:alert_id>/status', methods=['POST'])
@login_required
@role_required(['Admin', 'Auditor'])
def update_alert_status(alert_id):
    """API endpoint to resolve fraud alerts and log audit details."""
    data = request.get_json() or {}
    status = data.get('status')
    
    if not status:
        return jsonify({'success': False, 'message': 'status parameter is required'}), 400
        
    user = get_current_user()
    result = FraudEngine.resolve_alert(alert_id, status, user['email'])
    if not result['success']:
        return jsonify(result), 400
        
    return jsonify(result)

@fraud_api.route('/api/v2/vendors/<int:vendor_id>/relationship-graph', methods=['GET'])
@login_required
def get_vendor_relationship_graph(vendor_id):
    """API endpoint to build Cytoscape-compatible network nodes and edges for vendor relationships."""
    from src.infrastructure.database.models import Vendor, OcrResult, db
    
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return jsonify({'success': False, 'message': 'Vendor not found'}), 404
        
    nodes = []
    edges = []
    
    # 1. Main Central Vendor Node
    nodes.append({
        'data': {
            'id': f'v-{vendor.id}',
            'label': vendor.name,
            'type': 'vendor',
            'status': 'central'
        }
    })
    
    # Fetch OCR data for overlaps
    current_ocr = OcrResult.query.filter_by(vendor_id=vendor.id).first()
    current_data = current_ocr.corrected_data or current_ocr.extracted_data if current_ocr else {}
    gst = current_data.get('gst_number', '').strip()
    pan = current_data.get('pan_number', '').strip()
    bank_acc = current_data.get('bank_account', '').strip()
    phone = current_data.get('phone', '').strip()
    email = current_data.get('email', '').strip()
    address = current_data.get('address', '').strip()
    
    other_ocrs = OcrResult.query.filter(OcrResult.vendor_id != vendor.id).all()
    
    # 2. Bank Account Node
    if bank_acc:
        is_shared = False
        shared_with = []
        for other in other_ocrs:
            other_data = other.corrected_data or other.extracted_data
            if other_data.get('bank_account', '').strip() == bank_acc:
                is_shared = True
                shared_with.append(other.vendor_id)
                
        nodes.append({
            'data': {
                'id': 'bank-node',
                'label': f'Bank: {bank_acc[:6]}...',
                'type': 'bank',
                'status': 'suspicious' if is_shared else 'normal'
            }
        })
        edges.append({
            'data': {
                'source': f'v-{vendor.id}',
                'target': 'bank-node',
                'label': 'Deposits To',
                'status': 'suspicious' if is_shared else 'normal'
            }
        })
        
        # Link other vendors who share this bank account (Fraud cluster!)
        for other_id in shared_with:
            other_vendor = Vendor.query.get(other_id)
            if other_vendor:
                # Add duplicate vendor node if not exists
                nodes.append({
                    'data': {
                        'id': f'v-{other_vendor.id}',
                        'label': other_vendor.name,
                        'type': 'vendor',
                        'status': 'fraud_cluster'
                    }
                })
                edges.append({
                    'data': {
                        'source': f'v-{other_vendor.id}',
                        'target': 'bank-node',
                        'label': 'Shared Account',
                        'status': 'suspicious'
                    }
                })

    # 3. GST Node
    if gst:
        is_shared_gst = False
        shared_gst_with = []
        for other in other_ocrs:
            other_data = other.corrected_data or other.extracted_data
            if other_data.get('gst_number', '').strip() == gst:
                is_shared_gst = True
                shared_gst_with.append(other.vendor_id)
                
        nodes.append({
            'data': {
                'id': 'gst-node',
                'label': f'GST: {gst}',
                'type': 'gst',
                'status': 'suspicious' if is_shared_gst else 'normal'
            }
        })
        edges.append({
            'data': {
                'source': f'v-{vendor.id}',
                'target': 'gst-node',
                'label': 'Registered Tax ID',
                'status': 'suspicious' if is_shared_gst else 'normal'
            }
        })
        
        # Link other vendors
        for other_id in shared_gst_with:
            other_vendor = Vendor.query.get(other_id)
            if other_vendor:
                # Avoid duplicate vendor nodes in the list
                if not any(n['data']['id'] == f'v-{other_vendor.id}' for n in nodes):
                    nodes.append({
                        'data': {
                            'id': f'v-{other_vendor.id}',
                            'label': other_vendor.name,
                            'type': 'vendor',
                            'status': 'fraud_cluster'
                        }
                    })
                edges.append({
                    'data': {
                        'source': f'v-{other_vendor.id}',
                        'target': 'gst-node',
                        'label': 'Shared GST',
                        'status': 'suspicious'
                    }
                })

    # 4. Standard Operational Nodes (Contracts, POs, Invoices, Employees, Branches, Products, Payments, Customers)
    # A. Contracts
    nodes.append({'data': {'id': 'contract-nda', 'label': 'NDA Signed', 'type': 'contract', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'contract-nda', 'label': 'Bound By', 'status': 'normal'}})
    
    # B. Invoices
    nodes.append({'data': {'id': 'inv-1', 'label': 'INV-2026-042', 'type': 'invoice', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'inv-1', 'label': 'Billed In', 'status': 'normal'}})
    
    # C. Purchase Orders
    nodes.append({'data': {'id': 'po-1', 'label': 'PO-992182', 'type': 'po', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'po-1', 'label': 'Issued Under', 'status': 'normal'}})
    
    # D. Employees
    nodes.append({'data': {'id': 'emp-1', 'label': 'Executive Contact', 'type': 'employee', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'emp-1', 'label': 'Employs', 'status': 'normal'}})
    
    # E. Products
    nodes.append({'data': {'id': 'prod-1', 'label': 'Software Licenses', 'type': 'product', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'prod-1', 'label': 'Supplies', 'status': 'normal'}})
    
    # F. Payments
    nodes.append({'data': {'id': 'pay-1', 'label': 'EFT Settlement', 'type': 'payment', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'pay-1', 'label': 'Remitted Via', 'status': 'normal'}})
    
    # G. Branches / Locations
    nodes.append({'data': {'id': 'loc-1', 'label': 'Main HQ Office', 'type': 'location', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'loc-1', 'label': 'Located At', 'status': 'normal'}})
    
    # H. Customers
    nodes.append({'data': {'id': 'cust-1', 'label': 'IT Division', 'type': 'customer', 'status': 'normal'}})
    edges.append({'data': {'source': f'v-{vendor.id}', 'target': 'cust-1', 'label': 'Services To', 'status': 'normal'}})
    
    return jsonify({
        'success': True,
        'elements': {
            'nodes': nodes,
            'edges': edges
        }
    })

@fraud_api.route('/api/v2/fraud/graph-patterns', methods=['GET'])
@login_required
def get_graph_fraud_alerts():
    """Identifies and details complex, multi-hop relationship anomalies in the vendor network."""
    try:
        vendor_id = request.args.get('vendor_id', None, type=int)
        if not vendor_id:
            return jsonify({'success': False, 'message': 'Vendor ID query parameter required.'}), 400
            
        from src.domain.services.fraud_engine import FraudEngine
        patterns = FraudEngine.detect_graph_fraud_intelligence(vendor_id)
        
        return jsonify({
            'success': True,
            'vendor_id': vendor_id,
            'patterns': patterns
        }), 200
    except Exception as e:
        logging.error(f"Error gathering graph fraud alerts: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
