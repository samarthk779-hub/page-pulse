from flask import Blueprint, jsonify, render_template, request

from .audit import AuditError, run_audit

bp = Blueprint("routes", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/audit", methods=["POST"])
def audit():
    payload = request.get_json(silent=True) or {}
    raw_url = payload.get("url", "")

    try:
        report = run_audit(raw_url)
        return jsonify(report), 200
    except AuditError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception as exc:  # never crash — always return sensible JSON
        return jsonify({"error": f"Unexpected error: {exc}"}), 500
