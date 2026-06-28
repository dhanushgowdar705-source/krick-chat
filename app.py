import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
socketio = SocketIO(app, max_http_buffer_size=10_000_000, async_mode='eventlet')
rooms_users = {}
online_users = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'no file'}), 400
    filename = secure_filename(file.filename)
    unique_name = str(os.urandom(8).hex()) + '_' + filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(path)
    return jsonify({'url': '/' + path.replace('\\', '/')})

@socketio.on('register')
def handle_register(data):
    online_users[request.sid] = {'name': data['username'], 'phone': data['phone']}
    emit('online_users', list(online_users.values()), broadcast=True)

@socketio.on('join')
def handle_join(data):
    room = data['room']
    username = data['username']
    join_room(room)
    rooms_users.setdefault(room, {})[request.sid] = username
    emit('user_list', list(rooms_users[room].values()), room=room)
    emit('receive_message', {'user': 'System', 'text': username + ' joined', 'time': ''}, room=room)

@socketio.on('send_message')
def handle_message(data):
    emit('receive_message', data, room=data['room'])

@socketio.on('typing')
def handle_typing(data):
    emit('user_typing', data, room=data['room'], include_self=False)

@socketio.on('edit_message')
def handle_edit(data):
    emit('message_edited', data, room=data['room'], include_self=False)

@socketio.on('delete_message')
def handle_delete(data):
    emit('message_deleted', data, room=data['room'], include_self=False)

@socketio.on('message_seen')
def handle_seen(data):
    emit('message_seen_update', data, room=data['room'], include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        del online_users[request.sid]
        emit('online_users', list(online_users.values()), broadcast=True)
    for room, users in rooms_users.items():
        if request.sid in users:
            username = users.pop(request.sid)
            emit('user_list', list(users.values()), room=room)
            emit('receive_message', {'user': 'System', 'text': username + ' left', 'time': ''}, room=room)
            break

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)