
#!/usr/bin/env python3
import random
import itertools
from typing import List, Optional, Dict, Tuple
from uuid import uuid4

# --- Costanti ---
RANKS = "23456789TJQKA"
SUITS = "SHDC"
RANK_VALUE = {r: i+2 for i, r in enumerate(RANKS)} # 2-14 (A=14)
HAND_RANKS = [
    "High Card","One Pair","Two Pair","Three of a Kind","Straight",
    "Flush","Full House","Four of a Kind","Straight Flush"
]

# --- Classi di Base ---

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUE[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    def to_dict(self):
        return {"rank": self.rank, "suit": self.suit, "str": repr(self)}

class Deck:
    def __init__(self):
        self.cards = [Card(r,s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)
    def draw(self, n=1):
        drawn = self.cards[:n]
        self.cards = self.cards[n:]
        return drawn

class Player:
    def __init__(self, name):
        self.id = str(uuid4())[:8]
        self.name = name
        self.chips = 1000
        self.hole: List[Card] = []
        self.in_hand = True
        self.current_bet = 0
        self.all_in = False
    def to_public(self, reveal=False):
        return {
            "id": self.id,
            "name": self.name,
            "chips": self.chips,
            "in_hand": self.in_hand,
            "current_bet": self.current_bet,
            "all_in": self.all_in,
            "hole": [repr(c) for c in self.hole] if reveal else (len(self.hole) * ["XX"])
        }

# --- Funzioni di Valutazione ---

def is_straight(values):
    vals = sorted(set(values), reverse=True)
    # A-5 low straight (Aces are 1 or 14)
    if 14 in vals:
        vals.append(1)
    for i in range(len(vals)-4):
        window = vals[i:i+5]
        # Check if difference is 1 for 4 consecutive pairs
        if len(window) == 5 and all(window[j]-window[j+1]==1 for j in range(4)):
            return window[0] # Ritorna la carta alta della scala
    return None

def evaluate_5cards(cards: List[Card]):
    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    counts = {}
    for v in values:
        counts[v] = counts.get(v,0)+1
    # Ordina per conteggio discendente, poi per valore discendente
    by_count_then_value = sorted(counts.items(), key=lambda kv:(-kv[1], -kv[0]))

    # Straight Flush
    suit_counts = {}
    for c in cards:
        suit_counts.setdefault(c.suit, []).append(c.value)
    for s, vals in suit_counts.items():
        if len(vals) >= 5:
            fh = is_straight(sorted(vals, reverse=True))
            if fh:
                return (8, (fh,)) # (Rank Index, (High Card, ...))

    # Four of a Kind
    if by_count_then_value[0][1] == 4:
        four = by_count_then_value[0][0]
        kicker = max(v for v in values if v != four)
        return (7, (four, kicker))

    # Full House
    if by_count_then_value[0][1] == 3 and len(by_count_then_value) > 1 and by_count_then_value[1][1] >= 2:
        return (6, (by_count_then_value[0][0], by_count_then_value[1][0]))

    # Flush
    for s in SUITS:
        suited = sorted([c.value for c in cards if c.suit==s], reverse=True)
        if len(suited) >= 5:
            return (5, tuple(suited[:5]))

    # Straight
    straight_high = is_straight(values)
    if straight_high:
        return (4, (straight_high,))

    # Three of a Kind
    if by_count_then_value[0][1] == 3:
        three = by_count_then_value[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, (three,)+tuple(kickers))

    # Two Pair
    if by_count_then_value[0][1] == 2 and len(by_count_then_value) > 1 and by_count_then_value[1][1] == 2:
        hp = by_count_then_value[0][0]; lp = by_count_then_value[1][0]
        kicker = max(v for v in values if v != hp and v != lp)
        return (2, (hp, lp, kicker))

    # One Pair
    if by_count_then_value[0][1] == 2:
        pair = by_count_then_value[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, (pair,)+tuple(kickers))

    # High Card
    return (0, tuple(values[:5]))

def best_from_seven(seven):
    best = (-1, ())
    for combo in itertools.combinations(seven, 5):
        score = evaluate_5cards(list(combo))
        if score > best:
            best = score
    return best

# --- Classe di Gioco ---

class Game:
    def __init__(self, max_players=4, sb=10, bb=20):
        self.players: List[Player] = []
        self.max_players = max_players
        self.sb = sb
        self.bb = bb
        self.deck: Optional[Deck] = None
        self.community: List[Card] = []
        self.pot = 0
        self.dealer_idx = 0
        self.current_bet = 0
        self.turn_idx = 0
        self.started = False
        self.stage = "waiting"  # waiting, preflop, flop, turn, river, showdown
        self.last_raiser_idx = -1 # Traccia l'ultima persona che ha rilanciato/puntato

    def add_player(self, name) -> str:
        if len(self.players) >= self.max_players:
            raise Exception("Room full")
        p = Player(name)
        self.players.append(p)
        return p.id

    def find_player(self, pid) -> Optional[Player]:
        for p in self.players:
            if p.id == pid:
                return p
        return None

    def start_hand(self) -> Tuple[bool, str]:
        if len(self.players) < 2:
            return False, "Serve almeno 2 giocatori"
        
        # Filtra i giocatori senza fiches (per poter giocare)
        active_players = [p for p in self.players if p.chips > 0]
        if len(active_players) < 2:
            return False, "Non ci sono abbastanza giocatori con fiches."
        
        # Aggiorna la lista dei giocatori solo con quelli attivi per la mano
        self.players = active_players 
        
        # reset players
        for p in self.players:
            p.hole = []
            p.in_hand = True
            p.current_bet = 0
            p.all_in = False
            
        self.deck = Deck()
        self.community = []
        self.pot = 0
        self.current_bet = 0
        self.started = True
        self.stage = "preflop"
        
        # deal 2 cards
        for _ in range(2):
            for p in self.players:
                p.hole.append(self.deck.draw(1)[0])
                
        # post blinds
        self.dealer_idx = self.dealer_idx % len(self.players) # Assicura che l'indice sia valido
        sb_idx = (self.dealer_idx + 1) % len(self.players)
        bb_idx = (self.dealer_idx + 2) % len(self.players)
        
        sb_player = self.players[sb_idx]
        bb_player = self.players[bb_idx]
        
        sb_amt = min(self.sb, sb_player.chips)
        bb_amt = min(self.bb, bb_player.chips)
        
        sb_player.chips -= sb_amt; sb_player.current_bet = sb_amt
        sb_player.all_in = sb_player.chips == 0
        
        bb_player.chips -= bb_amt; bb_player.current_bet = bb_amt
        bb_player.all_in = bb_player.chips == 0

        self.pot += sb_amt + bb_amt
        self.current_bet = bb_amt
        
        # first to act is player after BB
        self.turn_idx = (bb_idx + 1) % len(self.players)
        self.last_raiser_idx = bb_idx # La BB è l'ultima "puntata" obbligatoria
        
        return True, "Mano iniziata"

    def advance_stage(self):
        # Metti tutte le current_bet nel pot
        total_bets = sum(p.current_bet for p in self.players)
        self.pot += total_bets
        
        if self.stage == "preflop":
            self.community.extend(self.deck.draw(3))
            self.stage = "flop"
        elif self.stage == "flop":
            self.community.extend(self.deck.draw(1))
            self.stage = "turn"
        elif self.stage == "turn":
            self.community.extend(self.deck.draw(1))
            self.stage = "river"
        elif self.stage == "river":
            self.stage = "showdown"
        else:
            # Dopo lo showdown, prepara il gioco per la prossima mano
            self.started = False
            self.stage = "waiting"
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
            return

        # reset current bets for next round
        for p in self.players:
            p.current_bet = 0
        self.current_bet = 0
        
        # next to act is player after dealer (first non-folded/non-all-in player)
        self.turn_idx = (self.dealer_idx + 1) % len(self.players)
        self.turn_idx = self.next_active_idx(self.turn_idx - 1) # Trova il primo attivo
        self.last_raiser_idx = -1 # Resetta l'ultimo raiser

    def public_state(self, player_id) -> Dict:
        # returns JSON-serializable state; reveals only player's own hole cards
        players_public = []
        for p in self.players:
            reveal = (p.id == player_id) or self.stage == "showdown"
            players_public.append(p.to_public(reveal=reveal))
        return {
            "players": players_public,
            "community": [c.to_dict() for c in self.community],
            "pot": self.pot,
            "stage": self.stage,
            "dealer_idx": self.dealer_idx,
            "current_bet": self.current_bet,
            "turn_id": self.players[self.turn_idx].id if self.players and self.started else None,
            "hand_started": self.started
        }

    def next_active_idx(self, start):
        n = len(self.players)
        # Cerca il prossimo giocatore attivo (in_hand AND non all_in)
        for i in range(1, n + 1):
            idx = (start + i) % n
            p = self.players[idx]
            # Giocatore è attivo se è in mano E deve ancora agire
            if p.in_hand and not p.all_in and p.current_bet < self.current_bet:
                return idx
        
        # Se non c'è nessuno che deve agire per chiamare la puntata,
        # cerca il primo non-fold/non-all-in come punto di partenza per il CHECK/BET
        if self.current_bet == 0:
             for i in range(1, n + 1):
                idx = (start + i) % n
                p = self.players[idx]
                if p.in_hand and not p.all_in:
                    return idx
        
        return None

    def is_betting_round_over(self):
        active_in_hand = [p for p in self.players if p.in_hand and not p.all_in]
        
        # Se tutti gli attivi hanno foldato, è finita
        if not active_in_hand:
            return True # Verrà gestito da all_but_one_folded
        
        # 1. Tutti i giocatori attivi (non fold/non all-in) devono avere la stessa current_bet
        if not all(p.current_bet == self.current_bet for p in active_in_hand):
            return False
            
        # 2. Tutti devono aver avuto l'opportunità di agire dopo l'ultimo raiser (o buio)
        # Questo è complesso da gestire con last_raiser_idx.
        # Semplificazione: se il turno è tornato all'ultimo raiser (o chi era alla sua sx)
        # E tutti gli altri hanno chiamato/foldato/all-in
        
        # Se self.current_bet > 0, il giro finisce quando il turno torna all'ultimo raiser
        # che è ancora in mano (escluso se è all-in)
        
        # La logica del tuo `player_action` che avanza il turno finché tutti hanno agito
        # può essere mantenuta, ma la condizione di fine è:
        # Quando il prossimo giocatore da agire (next_active_idx) è NESSUNO.
        
        # Controlla solo se tutti i giocatori in mano (anche all-in) sono pari alla puntata massima
        # O se sono all-in
        for p in self.players:
            if p.in_hand and p.current_bet < self.current_bet and p.chips > 0:
                return False # C'è un giocatore che deve ancora chiamare
                
        # Controlla che almeno due giocatori siano rimasti per avanzare (non essenziale, ma aiuta)
        if self.stage != "preflop" and len([p for p in self.players if p.in_hand]) < 2:
            return True
            
        return True


    def all_but_one_folded(self):
        inplay = [p for p in self.players if p.in_hand]
        return len(inplay) <= 1

    # Nota: Questa funzione non gestisce le Side Pot, assegna solo il piatto principale.
    def collect_pots_and_award(self):
        # Metti tutte le current_bet rimanenti nel pot finale
        total_bets = sum(p.current_bet for p in self.players)
        self.pot += total_bets
        
        inplay = [p for p in self.players if p.in_hand]
        results = []
        
        # 1. Un solo giocatore rimasto
        if len(inplay) == 1:
            winner = inplay[0]
            winner.chips += self.pot
            results.append({"winner_name": winner.name, "amount": self.pot, "hand": "Unico Rimasto"})
            self.pot = 0
            return results
        
        # 2. Showdown: Assegnazione Semplificata (senza side pots)
        best_score = None
        winners = []
        
        for p in inplay:
            seven = p.hole + self.community
            score = best_from_seven(seven)
            
            hand_type = HAND_RANKS[score[0]]
            
            if best_score is None or score > best_score:
                best_score = score
                winners = [(p, hand_type)]
            elif score == best_score:
                winners.append((p, hand_type))
        
        # Split pot
        split = self.pot // len(winners)
        remaining = self.pot % len(winners) # Gestione arrotondamento
        
        # Assegna il resto al primo vincitore nell'indice
        for i, (w, hand_type) in enumerate(winners):
            amount = split
            if i == 0:
                 amount += remaining
            w.chips += amount
            results.append({"winner_name": w.name, "amount": amount, "hand": hand_type})
            
        self.pot = 0
        return results

    def player_action(self, player_id, action, amount=0) -> Tuple[bool, str]:
        p = self.find_player(player_id)
        if not p: return False, "Player non trovato"
        if not p.in_hand: return False, "Hai già foldato"
        if not self.started: return False, "Mano non iniziata"
        if self.players[self.turn_idx].id != player_id: return False, "Non è il tuo turno"
        if p.all_in: return False, "Sei All-in, non puoi agire"

        action = action.lower()
        to_call = self.current_bet - p.current_bet
        
        # --- Fold ---
        if action == "fold":
            p.in_hand = False
            # Check for end of hand
            if self.all_but_one_folded():
                self.collect_pots_and_award()
                self.advance_stage() # Passa a "waiting"
                return True, "Hai foldato. Altri hanno foldato, mano terminata."
            
            # Avanza il turno
            nxt = self.next_active_idx(self.turn_idx)
            if nxt is None:
                 # Se foldando il giro è finito (tutti gli altri hanno chiamato/sono all-in)
                self.advance_stage()
            else:
                self.turn_idx = nxt
            return True, "Fold"

        # --- Check ---
        if action == "check":
            if to_call > 0:
                return False, "Non puoi checkare se c'è da chiamare"
            
            # Avanza il turno
            # Controlla se il giro è finito (il prossimo è None)
            nxt = self.next_active_idx(self.turn_idx)
            
            if nxt is None:
                self.advance_stage()
            else:
                self.turn_idx = nxt
            return True, "Check"

        # --- Call ---
        if action == "call":
            if to_call <= 0:
                return False, "Non c'è nulla da chiamare, usa 'check'."
                
            put = min(to_call, p.chips)
            
            p.chips -= put
            p.current_bet += put
            self.pot += put # Verrà trasferito nel pot principale alla fine del round
            
            if p.chips == 0:
                p.all_in = True

            # Avanza il turno
            nxt = self.next_active_idx(self.turn_idx)

            if nxt is None:
                self.advance_stage()
            else:
                self.turn_idx = nxt
            return True, f"Call {put}"

        # --- Raise ---
        if action == "raise":
            min_raise = self.current_bet + self.bb
            
            # Calcola la puntata totale che il giocatore deve mettere (non solo l'incremento)
            total_bet_required = p.current_bet + amount
            
            # Controllo: Se amount è solo l'incremento, deve essere almeno la BB o il precedente rilancio.
            # Qui si suppone che 'amount' sia il *totale* che il giocatore sta puntando.
            # Ma il tuo codice lo usa come *incremento* rispetto alla puntata attuale. Aderiamo a questo.
            
            if amount <= 0:
                 return False, "Specifica un importo di rilancio valido."
            
            # L'incremento del rilancio deve essere almeno il BB (o il rilancio precedente)
            min_inc = self.bb
            if self.current_bet > self.bb:
                # Trova il precedente rilancio effettivo (o BB)
                previous_bet = self.players[self.last_raiser_idx].current_bet if self.last_raiser_idx != -1 else 0
                min_inc = self.current_bet - previous_bet

            if amount < min_inc and amount < p.chips: # Solo se non è un all-in
                 return False, f"Il rilancio minimo deve essere di almeno {min_inc} in più del 'call'."
            
            to_put = to_call + amount # Totale da mettere = Call + Incremento
            
            if to_put >= p.chips:
                # All-in
                to_put = p.chips
                p.all_in = True
                new_bet = p.current_bet + to_put
                # Controlla se l'all-in è un rilancio valido o solo una chiamata incompleta
                if new_bet < min_raise and new_bet > self.current_bet:
                    # Rilancio inferiore al minimo (ma comunque un'azione valida in Hold'em)
                    # Non riapre la possibilità di rilanciare agli altri, ma lasciamo la logica semplice per ora.
                    pass 
                
            p.chips -= to_put
            p.current_bet += to_put
            self.pot += to_put
            
            # Aggiorna la puntata corrente del tavolo solo se è maggiore
            if p.current_bet > self.current_bet:
                self.current_bet = p.current_bet
                self.last_raiser_idx = self.turn_idx
            
            # Avanza il turno (ricomincia il giro dal prossimo attivo)
            nxt = self.next_active_idx(self.turn_idx)
            
            if nxt is None:
                self.advance_stage()
            else:
                self.turn_idx = nxt
                
            return True, f"Raised a {p.current_bet} (Messo: {to_put})"

        return False, "Azione non riconosciuta"

    # --- AGGIUNTA: Visualizzazione dello stato del tavolo ---
    def print_table(self, reveal_all=False, player_id=None):
        print("=" * 60)
        print(f"💰 POT TOTALE: {self.pot} | 🎲 FASE: {self.stage.upper()} | 📞 PUNTATA DA CHIAMARE: {self.current_bet}")
        
        community_str = " ".join([repr(c) for c in self.community]) if self.community else "[Nessuna Carta]"
        print(f"🃏 CARTE COMUNITARIE: {community_str}")
        print("-" * 60)
        
        print("GIOCATORI:")
        for idx, p in enumerate(self.players):
            
            is_dealer = "D" if idx == self.dealer_idx else " "
            is_sb = "SB" if idx == (self.dealer_idx + 1) % len(self.players) else " "
            is_bb = "BB" if idx == (self.dealer_idx + 2) % len(self.players) else " "
            
            pos = f"[{is_dealer}{is_sb}{is_bb}]"
            
            # Mostra le carte solo al proprio giocatore (o tutte in showdown)
            if reveal_all or self.stage == "showdown":
                hole_cards = " ".join([repr(c) for c in p.hole])
            elif player_id is not None and p.id == player_id:
                hole_cards = " ".join([repr(c) for c in p.hole])
            else:
                hole_cards = "XX XX"
            
            marker = "<- TURNO" if self.started and idx == self.turn_idx else ""
            status = ""
            if p.all_in: status = "ALL-IN"
            elif not p.in_hand: status = "FOLD"
            
            # Calcola quanto manca per chiamare
            to_call = self.current_bet - p.current_bet
            call_status = f"(Mancano: {max(0, to_call)} per chiamare)"
            
            print(f"{pos} {p.name} ({p.chips} chips) | Carte: {hole_cards} | Puntato: {p.current_bet} {call_status} {status} {marker}")
        print("=" * 60)

# --- Funzione Principale per l'Interazione ---

def main():
    game = Game(max_players=4, sb=10, bb=20)
    
    # Setup Giocatori (Input semplice)
    print("--- ♠️ Texas Hold'em (Console) ♣️ ---")
    num_players = 0
    while num_players < 2 or num_players > game.max_players:
        try:
            num_players = int(input(f"Quanti giocatori (2-{game.max_players})? "))
        except ValueError:
            continue

    player_names = []
    for i in range(num_players):
        name = input(f"Inserisci il nome del Giocatore {i+1}: ")
        player_names.append(name)
    
    player_ids = {}
    for name in player_names:
        player_id = game.add_player(name)
        player_ids[name] = player_id

    # Ciclo di gioco principale
    hand_num = 1
    while len([p for p in game.players if p.chips > 0]) >= 2:
        print(f"\n======== MANO {hand_num} ========")
        
        # Riordina i giocatori eliminando i bankrupt e spostando il dealer
        game.players = [p for p in game.players if p.chips > 0]
        if len(game.players) < 2:
            print("\nNon ci sono abbastanza giocatori con fiches per continuare.")
            break
        
        success, msg = game.start_hand()
        if not success:
            print(f"Errore: {msg}. Fine partita.")
            break
        
        # Ciclo di puntate (fino a showdown o fold)
        while game.started and game.stage != "showdown":
            print(f"\n--- Fase: {game.stage.upper()} ---")
            
            # Trova l'ID del giocatore di turno per mostrare solo le sue carte
            turn_player_id = game.players[game.turn_idx].id
            game.print_table(player_id=turn_player_id)

            current_player = game.players[game.turn_idx]
            
            # Se il giocatore è foldato o all-in (e non è l'unico rimasto), avanza il turno
            if not current_player.in_hand or current_player.all_in:
                 nxt = game.next_active_idx(game.turn_idx)
                 if nxt is None:
                     game.advance_stage()
                 else:
                     game.turn_idx = nxt
                 continue

            to_call = game.current_bet - current_player.current_bet
            
            print(f"\n➡️ TURNO DI {current_player.name}")
            print(f"Fiches: {current_player.chips} | Puntato nel round: {current_player.current_bet}")
            
            # Prompt azione
            valid_action = False
            while not valid_action:
                if to_call == 0:
                    action_prompt = f"Azione (check / bet <importo> / fold): "
                else:
                    max_raise = current_player.chips - to_call
                    action_prompt = f"Azione (call {to_call} / raise <incremento> (min: {game.bb}) / fold): "
                
                action_input = input(action_prompt).strip().split()
                if not action_input:
                    continue
                
                action = action_input[0].lower()
                amount = 0
                
                if len(action_input) > 1 and (action == "raise" or action == "bet"):
                    try:
                        amount = int(action_input[1])
                    except ValueError:
                        print("Importo non valido. Riprova.")
                        continue
                
                # Normalizza 'bet' a 'raise' con to_call=0
                if action == "bet":
                    if to_call > 0:
                        print("Devi usare 'call' o 'raise', non 'bet'.")
                        continue
                    action = "raise"
                
                # Esecuzione e gestione degli errori
                if action in ["fold", "check", "call", "raise"]:
                    success, msg = game.player_action(current_player.id, action, amount)
                    print(f"-> {msg}")
                    valid_action = success
                else:
                    print("Azione non riconosciuta (usa fold, check, call o raise/bet <importo>).")

            # Check se il betting round è terminato dopo l'azione valida
            if game.is_betting_round_over():
                 game.advance_stage()
            
            # Dopo l'azione, se la mano è ancora in corso e il giro è finito, avanza la fase
            # La logica è già in player_action e advance_stage, ma la condizione is_betting_round_over
            # può essere chiamata qui per forzare l'avanzamento se il giro è completato.
            
        # Assegnazione del piatto dopo lo showdown o il fold di tutti
        if not game.started or game.stage == "showdown":
            if game.started:
                 print("\n--- SHOWDOWN ---")
            else:
                 print("\n--- Mano Terminata per Fold ---")
                 
            game.print_table(reveal_all=True)
            winners = game.collect_pots_and_award()
            print("\n🏆 VINCITORI E ASSEGNAZIONE PIATTO:")
            for result in winners:
                print(f"- **{result['winner_name']}** vince **{result['amount']}** fiches con un **{result['hand']}**.")
            
            # Il dealer_idx è stato aggiornato in advance_stage o collect_pots_and_award
            hand_num += 1

    print("\n\n--- PARTITA TERMINATA ---")
    final_players = sorted([p for p in game.players if p.chips > 0], key=lambda p: p.chips, reverse=True)
    for p in final_players:
        print(f"Classifica: {p.name} con {p.chips} fiches.")


if __name__ == "__main__":
    main()
