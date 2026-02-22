#!/usr/bin/env python3
"""
Simple webhook bridge for artlu.run → OpenClaw
Listens on a port and forwards messages to OpenClaw using subprocess
"""

import subprocess
import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive webhook and forward to OpenClaw"""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Use OpenClaw CLI to send message to main session
        result = subprocess.run([
            'openclaw', 'message', 'send', 
            '--session', 'agent:main:main',
            '--message', message
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'response': result.stdout})
        else:
            return jsonify({'error': result.stderr}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'OpenClaw timeout'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)