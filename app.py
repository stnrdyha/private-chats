import os
import eventlet
eventlet.monkey_patch()


from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
from datetime import datetime
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'recovery1923')
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

room_locks = {}
room_members = {}

@app.route('/')
def index():
    room = request.args.get('room', '')
    return render_template('index.html', initial_room=room)

@socketio.on('join')
def on_join(data):
    room = data['room']
    password = data.get('password')
    username = data['username']
    
    if room not in room_locks:
        room_locks[room] = password
        room_members[room] = []
    
    if room_locks[room] == password:
        join_room(room)
        if request.sid not in room_members[room]:
            room_members[room].append(request.sid)
        emit('status', {'msg': f'{username} bergabung ke ruangan.'}, to=room)
        emit('update_user_count', {'count': len(room_members[room])}, to=room)
    else:
        emit('join_error', {'msg': 'Password ruangan salah!'}, to=request.sid)

@socketio.on('nuke_room_request')
def handle_nuke(data):
    room = data['room']
    if room in room_locks:
        del room_locks[room]
    if room in room_members:
        del room_members[room]

    emit('force_nuke', to=room)

def cleanup_room(room):
    if room in room_members and len(room_members[room]) == 0:
        if room in room_locks:
            del room_locks[room]
        if room in room_members:
            del room_members[room]

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    eventlet.sleep(10)
    
    for room, members in list(room_members.items()):
        if sid in members:
            members.remove(sid)
            emit('update_user_count', {'count': len(members)}, to=room)
            if len(members) == 0:
                eventlet.spawn_after(600, cleanup_room, room)
            break

@socketio.on('message')
def handle_message(data):
    data['time'] = datetime.now().strftime('%H:%M') 
    emit('new_message', data, to=data['room'])

@socketio.on('typing')
def handle_typing(data):
    emit('display_typing', data, to=data['room'], include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    emit('hide_typing', data, to=data['room'], include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    socketio.run(app, host='0.0.0.0', port=port)
