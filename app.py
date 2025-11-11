#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template, send_from_directory
from uuid import uuid4
from game import Game, Player
import time

app = Flask(__name__, static_folder="static", template_folder="templates")

# In-memory rooms: room_id -> Game
rooms = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/create_room", methods=["POST"])
def create_room():
    data = request.json or {}
    max_players = int(data.get("max_players", 4))
    room_id = str(uuid4())[:8]
    g = Game(max_players=max_players)
    rooms[room_id] = g
    return jsonify({"ok": True, "room_id": room_id})

@app.route("/api/join", methods=["POST"])
def join():
    data = request.json or {}
    room_id = data.get("room_id")
    name = data.get("name") or f"Player-{str(uuid4())[:4]}"
    if room_id not in rooms:
        return jsonify({"ok": False, "error": "Room not found"}), 404
    game = rooms[room_id]
    if game.started:
        return jsonify({"ok": False, "error": "Game already started"}), 400
    player_id = game.add_player(name)
    return jsonify({"ok": True, "player_id": player_id, "name": name})

@app.route("/api/start", methods=["POST"])
def start():
    data = request.json or {}
    room_id = data.get("room_id")
    if room_id not in rooms:
        return jsonify({"ok": False, "error": "Room not found"}), 404
    game = rooms[room_id]
    ok, msg = game.start_hand()
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    return jsonify({"ok": True})

@app.route("/api/state", methods=["GET"])
def state():
    room_id = request.args.get("room_id")
    player_id = request.args.get("player_id")
    if not room_id or room_id not in rooms:
        return jsonify({"ok": False, "error": "Room not found"}), 404
    game = rooms[room_id]
    state = game.public_state(player_id)
    return jsonify({"ok": True, "state": state})

@app.route("/api/action", methods=["POST"])
def action():
    data = request.json or {}
    room_id = data.get("room_id")
    player_id = data.get("player_id")
    act = data.get("action")
    amount = int(data.get("amount", 0))
    if not room_id or room_id not in rooms:
        return jsonify({"ok": False, "error": "Room not found"}), 404
    game = rooms[room_id]
    success, msg = game.player_action(player_id, act, amount)
    if not success:
        return jsonify({"ok": False, "error": msg}), 400
    return jsonify({"ok": True, "msg": msg})

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)