import React, { useEffect, useRef, useState } from 'react';

export default function App() {
  const [ws, setWs] = useState(null);
  const [connected, setConnected] = useState(false);
  const [roomId, setRoomId] = useState('room1');
  const [name, setName] = useState('Giocatore');
  const [players, setPlayers] = useState([]);
  const [myId, setMyId] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [messages, setMessages] = useState([]);
  const [hand, setHand] = useState(null); // we'll simulate giving the client its own hand locally after start

  const wsRef = useRef();

  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  function connect() {
    const url = (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.hostname + ':3001';
    const socket = new WebSocket(url);
    socket.onopen = () => { setConnected(true); addMsg('Connesso a ' + url); };
    socket.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === 'room:update') setPlayers(data.payload.players);
      if (data.type === 'game:update') setGameState(data.payload);
      if (data.type === 'game:result') addMsg('Risultato: winner=' + data.payload.winner);
      // in this simple demo the server doesn't send private hole cards; simulate when start
    };
    socket.onclose = () => { setConnected(false); addMsg('Disconnesso'); };
    wsRef.current = socket;
    setWs(socket);
  }

  function joinRoom() {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) connect();
    const sendJoin = () => {
      wsRef.current.send(JSON.stringify({ type: 'join', roomId, payload: { name } }));
      addMsg('Hai chiesto di entrare nella stanza ' + roomId);
    };
    // wait until socket is open
    if (!wsRef.current) return;
    if (wsRef.current.readyState === WebSocket.OPEN) sendJoin();
    else wsRef.current.addEventListener('open', sendJoin, { once: true });
  }

  function startGame() {
    if (!wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: 'start', roomId }));
    // simulate giving yourself a random hand locally (client-side only for demo)
    const deck = buildDeck(); shuffle(deck);
    const myHole = [deck.pop(), deck.pop()];
    setHand(myHole);
    addMsg('Partita iniziata — hai ricevuto le tue carte (private)');
  }

  function sendAction(action, amount=0) {
    if (!wsRef.current) return;
    const playerId = players.find(p => p.name === name)?.id || null;
    wsRef.current.send(JSON.stringify({ type: 'action', roomId, payload: { playerId, action, amount } }));
    addMsg('Azione inviata: ' + action + (amount ? (' ' + amount) : ''));
  }

  function addMsg(t) { setMessages(m => [t, ...m].slice(0,50)); }

  return (
    <div className="p-6 font-sans max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Texas Hold'em — Multiplayer (demo)</h1>

      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 border rounded">
          <h2 className="font-semibold">Connessione & Stanza</h2>
          <label className="block mt-2">Nome</label>
          <input className="border p-1 w-full" value={name} onChange={e=>setName(e.target.value)} />
          <label className="block mt-2">Room ID</label>
          <input className="border p-1 w-full" value={roomId} onChange={e=>setRoomId(e.target.value)} />
          <div className="mt-3 flex gap-2">
            <button className="px-3 py-1 rounded bg-indigo-600 text-white" onClick={joinRoom}>Entra nella stanza</button>
            <button className="px-3 py-1 rounded bg-green-600 text-white" onClick={startGame}>Inizia partita</button>
          </div>

          <div className="mt-3">
            <h3 className="font-medium">Giocatori nella stanza</h3>
            <ul>
              {players.map(p => <li key={p.id}>{p.name} <span className="text-xs text-gray-500">({p.id})</span></li>)}
            </ul>
          </div>
        </div>

        <div className="p-4 border rounded">
          <h2 className="font-semibold">Mano & Azioni</h2>
          <div className="mt-2">
            <div>Tue carte (client-side): {hand ? hand.join(' ') : '---'}</div>
            <div className="mt-2">Community: {gameState ? (gameState.community||[]).join(' ') : '---'}</div>
            <div className="mt-2">Pot: {gameState ? gameState.pot : 0}</div>
            <div className="mt-3 flex gap-2">
              <button className="px-2 py-1 border rounded" onClick={()=>sendAction('check')}>Check</button>
              <button className="px-2 py-1 border rounded" onClick={()=>sendAction('call', 10)}>Call 10</button>
              <button className="px-2 py-1 border rounded" onClick={()=>sendAction('raise', 20)}>Raise 20</button>
              <button className="px-2 py-1 border rounded" onClick={()=>sendAction('fold')}>Fold</button>
            </div>
          </div>

        </div>
      </div>

      <div className="mt-6 p-4 border rounded">
        <h2 className="font-semibold">Log</h2>
        <div className="h-32 overflow-auto bg-gray-50 p-2">
          {messages.map((m,i) => <div key={i} className="text-sm">{m}</div>)}</div>
        </div>

      <div className="mt-6 text-xs text-gray-600">
        <strong>Nota:</strong> Questo è un demo. Per un gioco reale servono molte altre regole (blinds, turni rigorosi, gestione soldi/stack, sicurezza, anti-cheat).
      </div>
    </div>
  );
}

// small client helpers (deck) — used only for demo local hand generation
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
