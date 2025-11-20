let roomInput = document.getElementById("room");
let nameInput = document.getElementById("name");
let createBtn = document.getElementById("create");
let joinBtn = document.getElementById("join");
let startBtn = document.getElementById("start");
let meDiv = document.getElementById("me");
let playersDiv = document.getElementById("players");
let communityDiv = document.getElementById("community");
let controlsDiv = document.getElementById("controls");

let room_id = null;
let player_id = null;
let my_name = null;

createBtn.onclick = async () => {
  let res = await fetch("/api/create_room", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({})});
  let j = await res.json();
  if (j.ok) { 
    room_id = j.room_id; 
    roomInput.value = room_id; 
    // Sostituisci alert() con un messaggio nell'interfaccia utente (se possibile), ma per ora usiamo alert()
    alert("Stanza creata: " + room_id); 
  }
}
joinBtn.onclick = async () => {
  room_id = roomInput.value.trim();
  my_name = nameInput.value.trim() || "Guest";
  let res = await fetch("/api/join", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({room_id, name: my_name})});
  let j = await res.json();
  if (j.ok) {
    player_id = j.player_id;
    alert("Sei dentro come " + my_name);
  } else {
    alert("Errore: " + j.error);
  }
}
startBtn.onclick = async () => {
  if (!room_id) { alert("Inserisci room"); return; }
  let res = await fetch("/api/start", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({room_id})});
  let j = await res.json();
  if (!j.ok) alert("Errore: " + j.error); else alert("Mano iniziata");
}

async function poll() {
  if (!room_id || !player_id) return;
  
  try {
    let res = await fetch(`/api/state?room_id=${room_id}&player_id=${player_id}`);
    let j = await res.json();
    if (!j.ok) { 
      console.error("Errore polling stato:", j.error); 
      return; 
    }
    let s = j.state;
    renderState(s);
  } catch (error) {
    console.error("Errore di rete durante il polling:", error);
  }
}

function renderState(s) {
  // Informazioni del giocatore locale
  let my = s.players.find(p=>p.id===player_id);
  // Utilizza my.hole_ascii (già renderizzato come ASCII Art a 5 righe)
  if (my) {
    meDiv.innerHTML = `
      <strong>Tu: ${my.name}</strong> 
      Chips: ${my.chips} 
      Bet Corrente: ${my.current_bet}
      <br>
      <pre class="card-ascii">${my.hole_ascii}</pre>
    `;
  } else {
    meDiv.innerHTML = "Non sei in stanza o il tuo ID non è valido.";
  }
  
  // Giocatori al tavolo
  playersDiv.innerHTML = "<h2>Giocatori al Tavolo</h2>";
  s.players.forEach(p=>{
    // p.hole_ascii contiene la stringa ASCII corretta (nascosta o rivelata)
    let el = document.createElement("div");
    el.className = "player" + (p.id === s.turn_id ? " current-turn" : "");

    el.innerHTML = `
      <div>${p.name}${p.id===s.players[s.dealer_idx]?.id ? " (**D**)" : ""}</div>
      <div>Chips: ${p.chips}</div>
      <div>Bet: ${p.current_bet} / Contribuzione Totale: ${p.total_contribution}</div>
      <div>Status: ${p.in_hand ? "In Mano" : "Fold"}${p.all_in ? " (ALL-IN)" : ""}</div>
      <div>Hole: <pre class="card-ascii">${p.hole_ascii}</pre></div>
    `;
    playersDiv.appendChild(el);
  });
  
  // Community Cards
  // Utilizza s.community_ascii
  communityDiv.innerHTML = `
    <h3>Community (${s.stage}) - Pot: ${s.pot}</h3>
    <pre class="card-ascii">${s.community_ascii}</pre>
  `;
  
  // Controlli
  controlsDiv.innerHTML = "";
  if (s.turn_id === player_id) {
    let requiredCall = s.required_call || 0;
    
    let callText = requiredCall > 0 ? `Call ${requiredCall}` : 'Check';
    let minRaise = s.last_raise_amount + requiredCall; // Raise deve essere il doppio del last_raise_amount (o BB) + il call
    
    let fold = document.createElement("button");
    fold.innerText = "Fold"; fold.onclick = ()=>doAction("fold");
    
    let callOrCheck = document.createElement("button");
    callOrCheck.innerText = callText; 
    callOrCheck.onclick = ()=>doAction(requiredCall > 0 ? "call" : "check");
    
    let raise = document.createElement("button");
    raise.innerText = `Raise (Min ${minRaise})`; 
    raise.onclick = ()=> {
      let amt = prompt(`Quanto vuoi rilanciare in totale? (Minimo raise to ${minRaise + requiredCall})`);
      if (!amt) return;
      doAction("raise", parseInt(amt,10));
    };
    
    controlsDiv.appendChild(fold); 
    controlsDiv.appendChild(callOrCheck); 
    
    if (my.chips > requiredCall) {
      controlsDiv.appendChild(raise);
    }
    
  } else {
    let current = s.players.find(p => p.id === s.turn_id);
    let turnName = current ? current.name : "Nessuno";
    controlsDiv.innerHTML = `**Turno di: ${turnName}** (Required Call: ${s.required_call || 0})`;
  }
}

async function doAction(action, amount=0) {
  try {
    let res = await fetch("/api/action", {
      method:"POST", 
      headers:{"Content-Type":"application/json"}, 
      body:JSON.stringify({room_id, player_id, action, amount})
    });
    let j = await res.json();
    if (!j.ok) {
      // Sostituisci alert() con un modal/messaggio
      console.error("Errore azione: ", j.error);
      alert("Errore: " + j.error);
    } else {
      console.log("Azione successiva:", j.msg);
    }
    // Aggiorna rapidamente dopo l'azione
    poll();
  } catch (error) {
    console.error("Errore di rete durante l'azione:", error);
    alert("Errore di connessione. Riprova.");
  }
}

// Inizio del polling
setInterval(poll, 1000);