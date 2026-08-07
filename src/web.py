"""
Flask Web Application for Financial Metrics Chatbot
Tab 1: Interactive chatbot with visualizations
Tab 2: Raw database browser
"""

import os
import threading

from flask import Flask, render_template, request, jsonify

from .chatbot import FinancialChatbot
from .db_backend import get_connection, backend_name, is_cloud_configured

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder=os.path.join(ROOT_DIR, 'templates'))

# Chatbot access is serialized with a lock because the underlying
# SQLite connection is shared across Flask's request threads.
chatbot = None
chatbot_lock = threading.Lock()


def get_chatbot():
    global chatbot
    if chatbot is None:
        chatbot = FinancialChatbot()
    return chatbot


def get_db_connection():
    """Create a database connection for the current request.
    Cloud (Turso) if configured, otherwise the local read-only file."""
    return get_connection(readonly=True)


@app.route('/')
def index():
    """Render main interface with tabs"""
    return render_template('index.html')


@app.route('/status')
def status():
    """Report which database backend this deployment is using."""
    info = {
        'backend': backend_name(),
        'cloud': is_cloud_configured(),
    }
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM companies")
            info['companies'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM all_metrics")
            info['metrics'] = cursor.fetchone()[0]
            info['database_ok'] = True
        finally:
            conn.close()
    except Exception as e:
        info['database_ok'] = False
        info['error'] = str(e)
    return jsonify(info)


# ---------------------------------------------------------------------------
# Chatbot endpoints
# ---------------------------------------------------------------------------

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    with chatbot_lock:
        result = get_chatbot().chat(user_message)

    return jsonify({
        'response': result['response'],
        'chart_type': result['chart_type'],
        'chart_config': result['chart_config']
    })


@app.route('/companies')
def get_companies():
    """Get list of all companies"""
    with chatbot_lock:
        companies = get_chatbot().companies
    return jsonify({'companies': companies})


@app.route('/examples')
def get_examples():
    """Get example queries"""
    examples = [
        "Show me an overview of all companies",
        "Compare profitability across all companies",
        "Show NVDA revenue trend over time",
        "What are the latest metrics for TSLA?",
        "Show me GOOG's financial performance",
        "Compare revenue of all companies",
        "What's AMD's net margin?",
        "Show CRM historical data",
        "Show SPCX revenue by segment",
        "Break down SpaceX revenue into Starlink, launches, and AI",
    ]
    return jsonify({'examples': examples})


# ---------------------------------------------------------------------------
# Database browser endpoints
# ---------------------------------------------------------------------------

@app.route('/db/tables')
def db_tables():
    """List all tables and views with row counts"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
            "AND name != 'sqlite_sequence' "
            "ORDER BY type, name"
        )
        entries = cursor.fetchall()
        tables = []
        for name, kind in entries:
            cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
            count = cursor.fetchone()[0]
            tables.append({'name': name, 'rows': count, 'kind': kind})
        return jsonify({'tables': tables})
    finally:
        conn.close()


@app.route('/db/table/<table_name>')
def db_table(table_name):
    """Get rows from a table with pagination"""
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = max(int(request.args.get('offset', 0)), 0)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Validate name against actual tables/views to prevent SQL injection
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
        )
        valid_tables = {row[0] for row in cursor.fetchall()}
        if table_name not in valid_tables:
            return jsonify({'error': f'Table {table_name} not found'}), 404

        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        total = cursor.fetchone()[0]

        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []

        data = [list(row) for row in rows]

        return jsonify({
            'table': table_name,
            'columns': columns,
            'rows': data,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        conn.close()


@app.route('/db/query', methods=['POST'])
def db_query():
    """Run a custom read-only SQL query"""
    data = request.json
    sql = (data.get('sql') or '').strip()

    if not sql:
        return jsonify({'error': 'No SQL provided'}), 400

    # Only allow read-only SELECT queries
    lowered = sql.lower().lstrip('( \n\t')
    if not (lowered.startswith('select') or lowered.startswith('with')):
        return jsonify({'error': 'Only SELECT queries are allowed'}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchmany(500)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        data_rows = [list(row) for row in rows]
        return jsonify({
            'columns': columns,
            'rows': data_rows,
            'row_count': len(data_rows),
            'truncated': len(data_rows) == 500
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()