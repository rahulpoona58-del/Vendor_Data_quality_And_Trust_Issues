from flask import Flask, render_template, request
from model import get_vendor, get_all_vendors, get_top_vendors, generate_chart

app = Flask(__name__)


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