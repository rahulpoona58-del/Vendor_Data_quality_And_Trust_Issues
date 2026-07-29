from flask import render_template, request
from src import create_app
from model import get_vendor, get_all_vendors, get_top_vendors, generate_chart

app = create_app()


@app.route('/')
def home():
    return render_template("index.html")

#  FORM RESULT (POST)
@app.route('/result', methods=['POST'])
def result():
    try:
        vendor_id = request.form.get('vendor_id')

        if not vendor_id:
            return render_template("error.html", message="Please enter Vendor ID")

        vendor_id = int(vendor_id)

        if vendor_id < 0:
            return render_template("error.html", message="Invalid Vendor ID")

        vendor = get_vendor(vendor_id)

        if not vendor:
            return render_template("error.html", message="Vendor not found")

        return render_template("result.html", vendor=vendor)

    except ValueError:
        return render_template("error.html", message="Only numbers allowed")

    except Exception as e:
        return render_template("error.html", message=str(e))


#  NEW: DYNAMIC RESULT LINK
@app.route('/result/<int:vendor_id>')
def result_link(vendor_id):

    vendor = get_vendor(vendor_id)

    if not vendor:
        return render_template("error.html", message="Vendor not found")

    return render_template("result.html", vendor=vendor)


#  DASHBOARD
@app.route('/dashboard')
def dashboard():
    vendors = get_all_vendors()
    return render_template("dashboard.html", vendors=vendors)

@app.route('/executive-dashboard')
def executive_dashboard():
    return render_template("executive_dashboard.html")

@app.route('/demo')
def demo_portal():
    return render_template("demo.html")

@app.route('/geographic-analytics')
def geographic_analytics():
    return render_template("geographic_dashboard.html")

@app.route('/xai-dashboard')
def xai_dashboard():
    return render_template("xai_dashboard.html")

@app.route('/vendor-360')
def vendor_360():
    return render_template("vendor_360.html")

@app.route('/knowledge-graph')
def knowledge_graph():
    return render_template("knowledge_graph_dashboard.html")

@app.route('/fraud-investigator')
def fraud_investigator():
    return render_template("fraud_investigation_dashboard.html")

@app.route('/data-lineage')
def data_lineage():
    return render_template("data_lineage_dashboard.html")

@app.route('/anomaly-investigator')
def anomaly_investigator():
    return render_template("anomaly_dashboard.html")

@app.route('/reputation-console')
def reputation_console():
    return render_template("reputation_dashboard.html")

@app.route('/digital-twin')
def digital_twin():
    return render_template("digital_twin_dashboard.html")

@app.route('/what-if-simulator')
def what_if_simulator():
    return render_template("what_if_simulator.html")

@app.route('/investigator-workspace')
def investigator_workspace():
    return render_template("investigator_workspace.html")

@app.route('/command-center')
def command_center():
    return render_template("command_center.html")

@app.route('/semantic-search')
def semantic_search():
    return render_template("semantic_search.html")

@app.route('/debug-key')
def debug_key():
    from src.config import get_config
    c = get_config()
    return f"App config key: {app.config.get('SECRET_KEY')} | Config key: {c.SECRET_KEY}"

#  TOP VENDORS
@app.route('/top')
def top():
    vendors = get_top_vendors()
    return render_template("dashboard.html", vendors=vendors)


#  CHART
@app.route('/chart')
def chart():
    generate_chart()
    return render_template("chart.html")


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')