"""
Local development entrypoint.

Run with: python3 app.py
The Flask application itself lives in src/web.py.
"""

from src.web import app

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
