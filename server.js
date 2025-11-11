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

      // If only one player not folded, end hand
      const active = s.playersOrder.filter(id => !s.folded[id]);
      if (active.length === 1) {
        broadcast(roomId, { type: 'game:result', payload: { winner: active[0] } });
        r.state = null; // reset
      }
    }

  });

  ws.on('close', function() {
    const meta = ws._meta;
    if (!meta) return;
    const { roomId, id } = meta;
    const r = rooms[roomId];
    if (!r) return;
    r.players = r.players.filter(p => p.id !== id);
    broadcast(roomId, { type: 'room:update', payload: { players: r.players.map(p => ({ id: p.id, name: p.name })) } });
  });
});

// helper functions
function buildDeck() {
  const suits = ['s','h','d','c'];
  const ranks = ['2','3','4','5','6','7','8','9','T','J','Q','K','A'];
  const deck = [];
  for (const s of suits) for (const r of ranks) deck.push(r + s);
  return deck;
}
function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
}
function sanitizeStateForClients(s) {
  // don't reveal others' hole cards
  return {
    community: s.community,
    pot: s.pot,
    bets: s.bets,
    folded: s.folded,
    // we will NOT send hands; clients will get their own hole cards via a private message in a real server
  };
}