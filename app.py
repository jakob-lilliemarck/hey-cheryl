from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong secret key
socketio = SocketIO(app)

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    """Handles new WebSocket connections."""
    print('Client connected')
    emit('my response', {'data': 'Connected to server!'})  # Send a welcome message

@socketio.on('disconnect')
def test_disconnect():
    """Handles WebSocket disconnections."""
    print('Client disconnected')

@socketio.on('my event')
def handle_my_custom_event(json):
    """Handles incoming WebSocket messages and sends a response."""
    print('received json: ' + str(json))
    emit('my response', {'data': 'Server received: ' + json['data']})  # Echo the received data

if __name__ == '__main__':
    socketio.run(app, debug=True) # Set debug=False for production
