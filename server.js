/*
Project: Texas Hold'em (4 players) — minimal multiplayer example
Files included (this single file contains both client and server code & instructions):


1) server.js (Node.js + ws) -> simple WebSocket-based game server / authoritative state
2) client (this React component) -> connects to server, shows lobby, seats, game play


Notes / assumptions:
- Designed for 4 players (you + 3 amici). Create a room code and share the URL + room code.
- Server runs on port 3001 by default. Client assumes server is ws://<host>:3001
- This is an educational minimal implementation: it handles seating, dealing, basic betting rounds (check/call/raise/fold) and showdown with a hand-evaluator included.
- No persistent storage, no authentication, not hardened for production. Use on a trusted LAN or behind proper auth in production.


How to run:
1) Create a project folder and save two files: server.js and App.jsx (client file contents below).
2) Server:
- npm init -y
- npm install ws
- node server.js
3) Client (React + Tailwind):
- create-react-app or Vite. Place App.jsx as your main component.
- Ensure Tailwind is configured (optional — styles will still work without Tailwind but look better with it).
- Run the dev server. Open the same host in 4 browser tabs or on your friends' devices and join the same room code.


--- server.js ---
// Save from here to server.js
const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 3001 });
console.log('WebSocket server running on ws://0.0.0.0:3001');


const rooms = {}; // roomId -> { players: [{id, name, ws}], state }


function broadcast(roomId, msg) {
const r = rooms[roomId];
if (!r) return;
r.players.forEach(p => {
if (p.ws.readyState === WebSocket.OPEN) p.ws.send(JSON.stringify(msg));
});
}


wss.on('connection', function connection(ws) {
ws.on('message', function incoming(raw) {
let data;
try { data = JSON.parse(raw); } catch (e) { return; }
const { type, roomId, payload, playerId } = data;


if (type === 'join') {
if (!rooms[roomId]) rooms[roomId] = { players: [], state: null };
const id = Math.random().toString(36).slice(2,9);
rooms[roomId].players.push({ id, name: payload.name || ('Player-'+id), ws });
ws._meta = { roomId, id };
broadcast(roomId, { type: 'room:update', payload: { players: rooms[roomId].players.map(p => ({ id: p.id, name: p.name })) } });
}


if (type === 'leave') {
const r = rooms[roomId];
if (!r) return;
r.players = r.players.filter(p => p.id !== playerId);
broadcast(roomId, { type: 'room:update', payload: { players: r.players.map(p => ({ id: p.id, name: p.name })) } });
}


if (type === 'start') {
// initialize a fresh game state
const r = rooms[roomId];
if (!r) return;
// minimal authoritative shuffle + deal
const deck = buildDeck();
shuffle(deck);
const hands = {};
r.players.slice(0,4).forEach(p => {
hands[p.id] = [deck.pop(), deck.pop()];
});
const community = [deck.pop(), deck.pop(), deck.pop(), deck.pop(), deck.pop()];
r.state = { deck, hands, community, pot: 0, bets: {}, folded: {}, turnIndex: 0, playersOrder: r.players.slice(0,4).map(p => p.id) };
broadcast(roomId, { type: 'game:update', payload: sanitizeStateForClients(r.state) });
}


if (type === 'action') {
const r = rooms[roomId];
if (!r || !r.state) return;
// payload: { playerId, action: 'fold'|'check'|'call'|'raise', amount }
const s = r.state;
// naive action processing — no strict turn enforcement in this minimal example
const pid = payload.playerId;
if (payload.action === 'fold') s.folded[pid] = true;
if (payload.action === 'raise') { s.pot += payload.amount || 0; s.bets[pid] = (s.bets[pid]||0) + (payload.amount||0); }
if (payload.action === 'call') { s.pot += payload.amount || 0; s.bets[pid] = (s.bets[pid]||0) + (payload.amount||0); }
broadcast(roomId, { type: 'game:update', payload: sanitizeStateForClients(s) });
