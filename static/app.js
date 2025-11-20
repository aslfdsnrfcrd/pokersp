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

/**
 * Converte una carta nel formato "VALORESEME" (es. "As", "10c") in ASCII Art.
 * Se la carta è coperta (es. "XX"), mostra il dorso.
 * @param {string} card - La stringa della carta (es. "As", "10c", "XX").
 * @returns {string[]} Un array di stringhe, una per riga dell'ASCII art.
 */
function cardToAsciiArt(card) {
  const lines = 6; // Numero di righe per ogni carta
  
  if (card === "XX") {
    // Dorso della carta (coperta)
    return [
      " _____ ",
      "|#####|",
      "|#####|",
      "|#####|",
      "|#####|",
      " `-----' "
    ];
  }

  const value = card.length > 2 ? card.substring(0, card.length - 1) : card[0];
  const suit = card[card.length - 1]; // es. 's', 'c', 'h', 'd'

  let symbol;
  let colorClass;
  // Uso delle entità HTML numeriche per i semi
  switch (suit) {
    case 's': symbol = '&#9824;'; colorClass = 'card-black'; break; // Picche (♠)
    case 'c': symbol = '&#9827;'; colorClass = 'card-black'; break; // Fiori (♣)
    case 'h': symbol = '&#9829;'; colorClass = 'card-red'; break; // Cuori (♥)
    case 'd': symbol = '&#9830;'; colorClass = 'card-red'; break; // Quadri (♦)
    default: symbol = '?'; colorClass = 'card-black'; break;
  }

  // Normalizza il valore per la visualizzazione (T per 10)
  const displayValue = (value === '10' ? 'T' : value.toUpperCase()).padEnd(2, ' ');
  
  // ATTENZIONE: Qui ho usato template literal solo dove necessario per l'interpolazione
  return [
    `<span class="${colorClass}"> _____ </span>`,
    `<span class="${colorClass}">|${displayValue}. |</span>`,
    `<span class="${colorClass}">|     |</span>`, 
    `<span class="${colorClass}">|  ${symbol}  |</span>`, 
    `<span class="${colorClass}">|     |</span>`, 
    `<span class="${colorClass}">|.${displayValue}|</span>`,
  ];
}
/**
 * Converte un array di carte nel loro blocco di ASCII Art, affiancandole.
 * @param {string[]} cards - Array di stringhe delle carte.
 * @returns {string} Il blocco HTML formattato con le carte in ASCII Art.
 */
function cardsToAsciiBlock(cards) {
  if (cards.length === 0) return "";
  
  const cardArt = cards.map(c => cardToAsciiArt(c));
  const lines = cardArt[0].length; // Il numero di righe per carta (dovrebbe essere 6)
  let outputHtml = '<pre style="display:inline-block; margin:0;">'; // Usa <pre> per mantenere la formattazione a spaziatura fissa

  for (let i = 0; i < lines; i++) {
    const line = cardArt.map(art => art[i]).join(''); // Unisce la riga i di ogni carta
    outputHtml += line + '\n';
  }
  outputHtml += '</pre>';

  return outputHtml;
}


function renderState(s) {
  // me info
  let my = s.players.find(p=>p.id===player_id);
  // Ho aggiunto il blocco carte qui
  meDiv.innerHTML = my ? `<strong>Tu: ${my.name}</strong> Chips: ${my.chips} Bets: ${my.current_bet}<br>${cardsToAsciiBlock(my.hole)}` : "Non sei in stanza";
  
  // players
  playersDiv.innerHTML = "";
  s.players.forEach(p=>{
    // Se la mano è finita O il giocatore è ME stesso, mostro le carte. Altrimenti mostro "XX"
    const cardsToShow = (p.id === player_id || s.stage === "SHOWDOWN" || s.stage === "END") 
      ? p.hole 
      : p.hole.map(() => "XX"); 
    
    let el = document.createElement("div");
    el.className = "player";
    // Aggiungo una classe per distinguere il giocatore di turno
    if (p.id === s.turn_id) {
      el.classList.add('current-turn');
    }

    el.innerHTML = `<div>${p.name}${p.id===s.players[s.dealer_idx]?.id ? " (**D**)" : ""}</div>
      <div>Chips: ${p.chips}</div>
      <div>Bet: ${p.current_bet}</div>
      <div>Hole: ${cardsToAsciiBlock(cardsToShow)}</div>
      <div>In mano: ${p.in_hand ? "Sì":"No"}</div>`;
    playersDiv.appendChild(el);
  });
  
  // community
  // Ho aggiunto il blocco carte qui
  communityDiv.innerHTML = `<h3>Community (${s.stage})</h3>` + cardsToAsciiBlock(s.community.map(c=>c.str));
  
  // controls if my turn
  controlsDiv.innerHTML = "";
  if (s.turn_id === player_id) {
    let fold = document.createElement("button");
    fold.innerText = "Fold"; fold.onclick = ()=>doAction("fold");
    let check = document.createElement("button");
    check.innerText = "Check"; check.onclick = ()=>doAction("check");
    let call = document.createElement("button");
    call.innerText = "Call"; call.onclick = ()=>doAction("call");
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
