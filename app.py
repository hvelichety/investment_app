"""
Flask Web Application for Financial Metrics Chatbot
Tab 1: Interactive chatbot with visualizations
Tab 2: Raw database browser
"""

from flask import Flask, render_template, request, jsonify
from chatbot import FinancialChatbot
import sqlite3
import threading

app = Flask(__name__)

DB_PATH = "financial_metrics.db"

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
    """Create a new read-only database connection for the current request"""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Render main interface with tabs"""
    return render_template('index.html')


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
        "Show CRM historical data"
    ]
    return jsonify({'examples': examples})


# ---------------------------------------------------------------------------
# Database browser endpoints
# ---------------------------------------------------------------------------

@app.route('/db/tables')
def db_tables():
    """List all tables with row counts"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = []
        for row in cursor.fetchall():
            name = row['name']
            count = cursor.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append({'name': name, 'rows': count})
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

        # Validate table name against actual tables to prevent SQL injection
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        valid_tables = {row['name'] for row in cursor.fetchall()}
        if table_name not in valid_tables:
            return jsonify({'error': f'Table {table_name} not found'}), 404

        total = cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []

        data = [[row[col] for col in columns] for row in rows]

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
        data_rows = [[row[col] for col in columns] for row in rows]
        return jsonify({
            'columns': columns,
            'rows': data_rows,
            'row_count': len(data_rows),
            'truncated': len(data_rows) == 500
        })
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Financial Metrics Chatbot Web App")
    print("=" * 60)
    print("\n🌐 Starting server...")
    print("📊 Access the app at: http://localhost:5000")
    print("\n💬 Tab 1: Chatbot with interactive charts")
    print("🗄️  Tab 2: Raw database browser + SQL console")
    print("\nPress Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
