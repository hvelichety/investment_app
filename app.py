"""
Flask Web Application for Financial Metrics Chatbot
Interactive web interface with real-time visualizations
"""

from flask import Flask, render_template, request, jsonify
from chatbot import FinancialChatbot
import json

app = Flask(__name__)
chatbot = FinancialChatbot()


@app.route('/')
def index():
    """Render main chat interface"""
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Get response from chatbot
    result = chatbot.chat(user_message)
    
    return jsonify({
        'response': result['response'],
        'chart_type': result['chart_type'],
        'chart_config': result['chart_config']
    })


@app.route('/companies')
def get_companies():
    """Get list of all companies"""
    companies = chatbot.companies
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


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Financial Metrics Chatbot Web App")
    print("="*60)
    print("\n🌐 Starting server...")
    print("📊 Access the chatbot at: http://localhost:5000")
    print("\n💡 Example queries:")
    print("   - Show me an overview")
    print("   - Compare profitability")
    print("   - Show NVDA trends")
    print("\nPress Ctrl+C to stop\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
