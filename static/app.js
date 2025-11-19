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
  if (j.ok) { room_id = j.room_id; roomInput.value = room_id; alert("Stanza creata: " + room_id); }
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
  let res = await fetch(`/api/state?room_id=${room_id}&player_id=${player_id}`);
  let j = await res.json();
  if (!j.ok) { console.log("err", j.error); return; }
  let s = j.state;
  renderState(s);
}

function renderState(s) {
  // me info
  let my = s.players.find(p=>p.id===player_id);
  meDiv.innerHTML = my ? `<strong>Tu: ${my.name}</strong> Chips: ${my.chips} Bets: ${my.current_bet}` : "Non sei in stanza";
  // players
  playersDiv.innerHTML = "";
  s.players.forEach(p=>{
    let el = document.createElement("div");
    el.className = "player";
    el.innerHTML = `<div>${p.name}${p.id===s.players[s.dealer_idx]?.id ? " (D)" : ""}</div>
      <div>Chips: ${p.chips}</div>
      <div>Bet: ${p.current_bet}</div>
      <div>Hole: ${p.hole.join(" ")}</div>
      <div>In hand: ${p.in_hand ? "Sì":"No"}</div>`;
    playersDiv.appendChild(el);
  });
  // community
  communityDiv.innerHTML = `<h3>Community (${s.stage})</h3>` + s.community.map(c=>c.str).join(" ");
  // controls if my turn
  controlsDiv.innerHTML = "";
  if (s.turn_id === player_id) {
    let fold = document.createElement("button");
    fold.innerText = "Fold"; fold.onclick = ()=>doAction("fold");
    let check = document.createElement("button");
    check.innerText = "Check"; check.onclick = ()=>doAction("check");
    let call = document.createElement("button");
    call.Text = "Call"; call.onclick = ()=>doAction("call");
    let raise = document.createElement("button");
    raise.innerText = "Raise"; raise.onclick = ()=> {
      let amt = prompt("Quanto vuoi rilanciare (numero)?");
      if (!amt) return;
      doAction("raise", parseInt(amt,10));
    };
    controlsDiv.appendChild(fold); controlsDiv.appendChild(check); controlsDiv.appendChild(call); controlsDiv.appendChild(raise);
} else {
  let current = s.players.find(p => p.id === s.turn_id);
  let turnName = current ? current.name : "nessuno";
  controlsDiv.innerHTML = `Turno di: ${turnName}`;
}
}

async function doAction(action, amount=0) {
  let res = await fetch("/api/action", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({room_id, player_id, action, amount})});
  let j = await res.json();
  if (!j.ok) alert("Errore: " + j.error); else console.log(j.msg);
  // update quickly
  poll();
}

setInterval(poll, 1000);
