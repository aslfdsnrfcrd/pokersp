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
    "High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush"
]

# --- Mappa i semi e i rank per la visualizzazione ASCII ---
SUIT_SYMBOLS = {
    "S": "♠",
    "H": "♥",
    "D": "♦",
    "C": "♣",
}
RANK_DISPLAY = {
    "T": "10",
    "J": "J",
    "Q": "Q",
    "K": "K",
    "A": "A",
}
# Aggiungi i numeri da 2 a 9
for i in range(2, 10):
    RANK_DISPLAY[str(i)] = str(i)

# --- Utility ---
def normalize_rank(r: str) -> str:
    """Normalizza il rank della carta (es. '10' -> 'T')."""
    r = str(r).upper()
    if r == "10":
        return "T"
    return r

# --- Classi ---

class Card:
    """Rappresenta una singola carta."""
    def __init__(self, rank: str, suit: str):
        self.rank = normalize_rank(rank)
        self.suit = suit
        self.value = RANK_VALUE[self.rank]
        self.str = f"{self.rank}{self.suit}"
        self.display = f"{RANK_DISPLAY[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self):
        return self.str
    
    def __lt__(self, other):
        return self.value < other.value

    def to_dict(self):
        """Converte la carta in un dizionario per l'invio al client."""
        # Colore basato sul seme per il rendering
        color = "red" if self.suit in ("H", "D") else "black"
        return {"str": self.str, "display": self.display, "color": color}


class Deck:
    """Rappresenta il mazzo di 52 carte."""
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        self.reset()

    def reset(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)

    def deal(self, count: int = 1) -> List[Card]:
        """Distribuisce un certo numero di carte."""
        if len(self.cards) < count:
            raise ValueError("Mazzo esaurito!")
        return [self.cards.pop() for _ in range(count)]


class Player:
    """Rappresenta un giocatore al tavolo."""
    def __init__(self, name: str, chips: int = 1000):
        self.id = str(uuid4())
        self.name = name
        self.chips = chips
        self.hole: List[Card] = [] # Carte in mano
        self.bet_current_stage: int = 0 # Totale puntato in questo giro di puntate
        self.bet_total_hand: int = 0 # Totale puntato in tutta la mano (per side pot)
        self.in_hand: bool = True # Flag se il giocatore è ancora attivo nella mano
        self.is_all_in: bool = False # Flag se il giocatore è all-in
        self.last_action: Optional[str] = None # Ultima azione effettuata


    def to_dict(self, include_hole: bool = False) -> Dict:
        """Converte il giocatore in un dizionario per l'invio al client."""
        data = {
            "id": self.id,
            "name": self.name,
            "chips": self.chips,
            "bet_current_stage": self.bet_current_stage,
            "bet_total_hand": self.bet_total_hand,
            "in_hand": self.in_hand,
            "is_all_in": self.is_all_in,
            "last_action": self.last_action,
        }
        if include_hole:
            data["hole"] = [c.to_dict() for c in self.hole]
        else:
            data["hole"] = []
        return data


def best_from_seven(cards: List[Card]) -> Tuple:
    """
    Funzione per trovare la migliore mano di poker di 5 carte da 7 carte.
    Restituisce una tupla (rank_value, kicker_tuple).
    Il rank_value è un indice da 0 (High Card) a 8 (Straight Flush).
    """
    # [Image of Poker Hand Ranks]
    # Questa è una semplificazione. La logica completa è complessa e richiede una
    # libreria di valutazione mani. Qui usiamo una logica basilare solo per la demo.

    values = sorted([c.value for c in cards], reverse=True)
    ranks_set = set(values)
    
    # Esempio banale: Pair
    for r in ranks_set:
        if values.count(r) == 2:
            return (1, (r,)) # Rank 1: One Pair. In una vera implementazione servirebbero i kicker.

    # High Card
    return (0, tuple(values[:5]))


class Game:
    """Contiene lo stato del gioco e la logica."""
    def __init__(self, max_players: int = 4):
        self.max_players = max_players
        self.players: List[Player] = []
        self.deck = Deck()
        self.community: List[Card] = []
        self.pot: int = 0
        self.started: bool = False
        self.stage: str = "Pre-flop" # Pre-flop, Flop, Turn, River, Showdown
        self.turn_index: int = -1 # Indice del giocatore di turno
        self.turn_id: Optional[str] = None # ID del giocatore di turno
        self.dealer_index: int = -1 # Indice del dealer (per posizioni)
        self.max_bet_current_stage: int = 0 # Puntata più alta fatta in questo giro
        self.min_raise_amount: int = 0 # Minimo importo per un rilancio (semplificato)
        self.last_bet_size: int = 0 # Dimensione dell'ultima puntata/rilancio

    def add_player(self, name: str) -> Optional[str]:
        if len(self.players) < self.max_players:
            player = Player(name)
            self.players.append(player)
            return player.id
        return None

    def start_hand(self) -> Tuple[bool, str]:
        if len(self.players) < 2:
            return False, "Non ci sono abbastanza giocatori (minimo 2)."
        
        # 1. Reset
        self.started = True
        self.deck.reset()
        self.community = []
        self.pot = 0
        self.stage = "Pre-flop"
        self.max_bet_current_stage = 0
        self.min_raise_amount = 0
        self.last_bet_size = 0
        
        # Aggiorna il dealer (semplificato, solo un avanzamento ciclico)
        self.dealer_index = (self.dealer_index + 1) % len(self.players)
        
        active_players = [p for p in self.players if p.chips > 0]
        if len(active_players) < 2:
             return False, "Non ci sono abbastanza giocatori attivi."
        
        # 2. Reset Giocatori (solo i giocatori attivi)
        for p in self.players:
            p.hole = []
            p.bet_current_stage = 0
            p.bet_total_hand = 0
            p.in_hand = p.chips > 0 # Rimuovi i giocatori a 0 chips dalla mano
            p.is_all_in = False
            p.last_action = None

        # 3. Distribuzione
        for _ in range(2): # 2 carte a testa
            for p in self.players:
                if p.in_hand:
                    p.hole.extend(self.deck.deal())

        # 4. Blinds (Semplificato: Blind fisso a 10 e puntata iniziale)
        # La logica dei blinds (SB/BB) richiede la gestione delle posizioni,
        # qui usiamo una versione semplice. Il primo giocatore dopo il dealer paga il "Blind".
        
        # Giocatore subito dopo il dealer (indice ciclico)
        def get_next_active_player_index(start_index):
            for i in range(1, len(self.players) + 1):
                idx = (start_index + i) % len(self.players)
                if self.players[idx].in_hand:
                    return idx
            return -1 # Non dovrebbe succedere se ci sono >= 2 giocatori attivi

        small_blind_index = get_next_active_player_index(self.dealer_index)
        big_blind_index = get_next_active_player_index(small_blind_index)
        
        blind_amount = 10
        
        # Paga il BB
        bb_player = self.players[big_blind_index]
        bet_bb = min(blind_amount * 2, bb_player.chips)
        self.do_bet(bb_player, bet_bb)
        
        # Paga il SB
        sb_player = self.players[small_blind_index]
        bet_sb = min(blind_amount, sb_player.chips)
        self.do_bet(sb_player, bet_sb)
        
        self.max_bet_current_stage = bet_bb
        self.last_bet_size = bet_bb
        self.min_raise_amount = bet_bb # Il rilancio minimo deve essere l'importo del BB.

        # 5. Imposta il turno (il giocatore dopo il BB)
        self.turn_index = get_next_active_player_index(big_blind_index)
        self.turn_id = self.players[self.turn_index].id

        return True, f"Mano iniziata. Dealer: {self.players[self.dealer_index].name}, Turno: {self.players[self.turn_index].name}."
    
    
    def do_bet(self, player: Player, amount: int):
        """Logica interna per la puntata/rilancio/chiamata."""
        
        # Quanto il giocatore ha già messo in questo giro
        already_bet = player.bet_current_stage
        
        # Calcola l'importo da prelevare dai chips
        bet_delta = min(amount, player.chips + already_bet) # Non può puntare più di quanto ha in chips + quanto ha già puntato (per l'all-in)
        
        # Se il giocatore va All-in
        if player.chips <= bet_delta - already_bet:
            bet_delta = player.chips + already_bet
            player.is_all_in = True
            player.chips = 0
        else:
            player.chips -= (bet_delta - already_bet)
        
        # Aggiorna i totali
        player.bet_current_stage = bet_delta
        player.bet_total_hand += (bet_delta - already_bet)
        self.pot += (bet_delta - already_bet)
        
        return bet_delta


    def get_next_active_index(self, start_index: int) -> Optional[int]:
        """Trova l'indice del prossimo giocatore attivo (in_hand AND not is_all_in) a partire da start_index."""
        num_players = len(self.players)
        # Cerca il giocatore successivo, ciclando il tavolo
        for i in range(1, num_players + 1):
            next_idx = (start_index + i) % num_players
            p = self.players[next_idx]
            # Il prossimo giocatore di turno deve essere in mano (non fold) e non all-in
            if p.in_hand and not p.is_all_in:
                return next_idx
        # Se non si trova nessuno, significa che il giro è finito (o tutti fold/all-in)
        return None
    
    def is_betting_round_complete(self) -> bool:
        """Verifica se il giro di puntate è completo."""
        
        # Giocatori attivi (non fold e non all-in)
        active_players = [p for p in self.players if p.in_hand and not p.is_all_in]

        # Se solo un giocatore ha i chips ed è attivo (gli altri fold/all-in)
        if len(active_players) <= 1:
            return True # Il giro è finito.

        # Controlla se tutti i giocatori attivi hanno eguagliato la puntata massima
        all_called = True
        for p in self.players:
            if p.in_hand and not p.is_all_in:
                # Tutti i giocatori attivi devono aver messo l'importo massimo
                if p.bet_current_stage < self.max_bet_current_stage:
                    # Se c'è un giocatore attivo che non ha ancora chiamato la puntata massima, il giro continua.
                    all_called = False
                    break
        
        # Se tutti gli attivi hanno eguagliato, ma l'azione è tornata al PUNTATORE ORIGINALE (per il pre-flop post-blind)
        # o se tutti gli attivi hanno agito e la max_bet è eguagliata.
        if all_called:
            # Regola speciale per il pre-flop: l'azione non si ferma se il BB è il puntatore massimo e gli altri hanno limpato/foldato
            # Ma nella nostra implementazione semplificata, consideriamo che se tutti gli attivi hanno eguagliato la max_bet, il giro è concluso.
            return True

        # Se c'è una puntata/rilancio (max_bet > 0) e non tutti hanno chiamato, il giro continua
        return False


    def advance_turn_or_stage(self) -> Optional[str]:
        """Avanza il turno al prossimo giocatore o passa alla fase successiva."""

        # 1. Tenta di trovare il prossimo giocatore di turno
        next_turn_index = self.get_next_active_index(self.turn_index)
        
        if next_turn_index is not None:
            # Trovato il prossimo giocatore, ma...
            # Verifichiamo se il giro di puntate è completo PRIMA di assegnare il turno
            if self.is_betting_round_complete():
                # Il giro è completo, passa alla fase successiva
                return self._advance_stage()
            else:
                # Il giro non è completo, passa il turno al giocatore successivo
                self.turn_index = next_turn_index
                self.turn_id = self.players[self.turn_index].id
                return None # Turno avanzato
        else:
            # Nessun giocatore attivo rimanente (tutti fold/all-in)
            # Il giro di puntate è terminato.
            return self._advance_stage()


    def _advance_stage(self) -> Optional[str]:
        """Avanza alla fase successiva del gioco (Flop, Turn, River, Showdown)."""
        
        # Reset delle puntate correnti per la nuova fase
        for p in self.players:
            p.bet_current_stage = 0
            p.last_action = None
            
        self.max_bet_current_stage = 0
        self.last_bet_size = 0
        self.min_raise_amount = 0
        
        # Gestione del cambio di fase
        if self.stage == "Pre-flop":
            # Flop (3 carte)
            self.community.extend(self.deck.deal(3))
            self.stage = "Flop"
        elif self.stage == "Flop":
            # Turn (1 carta)
            self.community.extend(self.deck.deal(1))
            self.stage = "Turn"
        elif self.stage == "Turn":
            # River (1 carta)
            self.community.extend(self.deck.deal(1))
            self.stage = "River"
        elif self.stage == "River":
            # Showdown
            self.stage = "Showdown"
            self.turn_id = None
            return "Showdown" # La mano finisce
        
        # Imposta il turno per la nuova fase:
        # Dopo il pre-flop, l'azione inizia dal primo giocatore attivo dopo il dealer (Small Blind)
        
        def get_first_to_act_index():
            # Il primo a parlare è il primo giocatore attivo (in_hand and not all_in) dopo il dealer
            return self.get_next_active_index(self.dealer_index)

        # Trova il primo giocatore attivo per il nuovo giro
        self.turn_index = get_first_to_act_index()
        if self.turn_index is not None:
            self.turn_id = self.players[self.turn_index].id
        else:
            # Tutti i giocatori sono fold o all-in, si va direttamente allo showdown
            self.stage = "Showdown"
            self.turn_id = None
            return "Showdown"
        
        return f"Passaggio alla fase: {self.stage}" # Fase avanzata


    def do_action(self, player_id: str, action: str, amount: int = 0) -> Tuple[bool, str, Optional[str]]:
        """Esegue un'azione (fold, check, call, raise)."""
        if self.stage == "Showdown" or not self.turn_id:
            return False, "La mano è finita.", None
        
        if player_id != self.turn_id:
            return False, "Non è il tuo turno.", None
            
        player = self.players[self.turn_index]
        
        if not player.in_hand or player.is_all_in:
            return False, "Non puoi agire (fold o all-in).", None

        # Quanto deve chiamare per eguagliare la puntata massima
        to_call = self.max_bet_current_stage - player.bet_current_stage
        
        action = action.lower()
        
        if action == "fold":
            player.in_hand = False
            player.last_action = "Fold"
            
            # Controlla se rimane un solo giocatore in mano
            active_in_hand = [p for p in self.players if p.in_hand]
            if len(active_in_hand) <= 1:
                # Assegna il piatto e termina la mano immediatamente
                winner = active_in_hand[0]
                winner.chips += self.pot
                self.pot = 0
                self.turn_id = None
                self.stage = "Finished"
                return True, f"{winner.name} vince il piatto ({winner.chips} chips) per fold degli avversari.", "Showdown"
            
        elif action == "check":
            # AZIONE CORRETTA PER IL CHECK:
            # Il check è permesso SOLO se non c'è una puntata da eguagliare (to_call == 0)
            if to_call > 0:
                return False, f"Non puoi fare check. Devi eguagliare {to_call} chips.", None
            
            player.last_action = "Check"

        elif action == "call":
            if to_call == 0:
                # Chiamare una puntata di 0 è essenzialmente un check
                player.last_action = "Check"
            elif to_call > 0:
                call_amount = min(to_call, player.chips) # Non puoi chiamare più di quanto hai
                self.do_bet(player, player.bet_current_stage + call_amount)
                player.last_action = "Call"
            else:
                return False, "La puntata da eguagliare è già coperta.", None

        elif action == "raise":
            if amount < 0:
                return False, "L'importo del rilancio non può essere negativo.", None
                
            current_bet = player.bet_current_stage
            
            # L'importo totale della puntata del giocatore dopo il rilancio
            total_bet_after_raise = current_bet + amount
            
            # L'importo della puntata che il giocatore deve mettere OLTRE la puntata attuale
            # Esempio: max_bet=100, player_bet=50. Deve mettere 50 per chiamare + l'importo del rilancio.
            # L'importo del rilancio è l'incremento sulla max_bet, non l'importo totale.
            
            # Importo minimo del rilancio (almeno l'importo dell'ultima puntata/rilancio)
            # Se nessuno ha puntato, min_raise_amount = 0, il rilancio minimo è BB (es. 20)
            min_raise = self.last_bet_size if self.last_bet_size > 0 else 20
            
            # L'importo totale che il giocatore sta puntando (current_bet + amount) deve essere
            # almeno (max_bet_current_stage + min_raise)
            
            # Se to_call > 0, l'incremento di rilancio deve essere di almeno min_raise,
            # quindi l'importo totale della puntata deve essere almeno max_bet_current_stage + min_raise
            required_total_bet = self.max_bet_current_stage + min_raise
            
            if total_bet_after_raise < required_total_bet and player.chips > to_call:
                 # Se il giocatore ha chips sufficienti per un rilancio legale, ma non lo fa
                 # Se il giocatore è all-in, la puntata non è un rilancio completo e non resetta l'azione.
                 # Per semplicità, in questa demo, non permettiamo rilanci non full-raise
                 return False, f"Rilancio non valido. Il rilancio deve portare la tua puntata totale a almeno {required_total_bet} (attuale max: {self.max_bet_current_stage} + min_raise: {min_raise}).", None
            
            if total_bet_after_raise > player.chips + current_bet:
                return False, "Non hai chips sufficienti per questo rilancio.", None

            # Calcola la dimensione del rilancio (differenza tra la nuova max_bet e la vecchia max_bet)
            # Solo se è un vero rilancio (nuova puntata > max_bet_current_stage)
            
            new_max_bet = self.do_bet(player, total_bet_after_raise)
            player.last_action = "Raise"
            
            if new_max_bet > self.max_bet_current_stage:
                # È un vero rilancio, aggiorna lo stato del gioco
                self.last_bet_size = new_max_bet - self.max_bet_current_stage
                self.max_bet_current_stage = new_max_bet
                
                # Se è un rilancio, l'azione deve tornare a TUTTI i giocatori non all-in,
                # quindi il giro continua fino a quando non hanno chiamato il nuovo max_bet.

        else:
            return False, "Azione non valida.", None

        # 4. Avanza il turno o la fase
        stage_change_msg = self.advance_turn_or_stage()
        
        return True, f"{player.name} ha fatto {player.last_action}.", stage_change_msg


    def public_state(self, player_id: Optional[str] = None) -> Dict:
        """Restituisce lo stato del gioco per un determinato giocatore (per nascondere le carte)."""
        player_turn = self.players[self.turn_index] if self.turn_index != -1 else None

        # Trova il 'to_call' per il giocatore che sta richiedendo lo stato, se è il suo turno
        to_call = 0
        if player_id and self.turn_id == player_id:
            my_player = next((p for p in self.players if p.id == player_id), None)
            if my_player:
                 to_call = self.max_bet_current_stage - my_player.bet_current_stage


        state = {
            "started": self.started,
            "stage": self.stage,
            "pot": self.pot,
            "community": [c.to_dict() for c in self.community],
            "turn_id": self.turn_id,
            "turn_name": player_turn.name if player_turn else "Nessuno",
            "max_bet_current_stage": self.max_bet_current_stage,
            "to_call": to_call, # Solo rilevante se è il mio turno
            "players": [p.to_dict(include_hole=(p.id == player_id or self.stage == "Showdown")) for p in self.players],
        }
        return state


    def resolve_hand(self) -> List[Dict]:
        """Determina i vincitori e divide il piatto (semplificato, senza side pot)."""
        if self.stage != "Showdown":
            return []
            
        # Logica Side Pot (Semplificata)
        # Identifica tutti i giocatori che hanno messo soldi nel piatto e sono in mano
        contributors = sorted(
            [p for p in self.players if p.bet_total_hand > 0 and p.in_hand],
            key=lambda p: p.bet_total_hand
        )

        pots = []
        total_payout = 0
        
        # Inizia il side pot processing
        while contributors:
            # Il giocatore con il più piccolo bet_total_hand definisce la cap per questo pot
            cap = contributors[0].bet_total_hand
            current_pot_size = 0
            eligible_players = []

            # Calcola l'importo che ogni giocatore ha contribuito al pot attuale
            for p in contributors:
                contribution = min(cap, p.bet_total_hand)
                p.bet_total_hand -= contribution
                current_pot_size += contribution
                eligible_players.append(p)

            if current_pot_size > 0:
                pots.append({
                    "size": current_pot_size,
                    "cap": cap,
                    "eligible": eligible_players
                })
            
            # Rimuovi i giocatori che non hanno più chips da contribuire
            contributors = [p for p in contributors if p.bet_total_hand > 0]
            
        all_results = []
        
        # Risolvi ogni pot (dal più piccolo/principale al più grande/side)
        for pot in pots:
            eligible_in_hand = [p for p in pot["eligible"] if p.in_hand]
            
            if not eligible_in_hand:
                continue

            pot_size = pot["size"]
            best_score = (-1, ())
            winners_for_pot = []
            
            for p in eligible_in_hand:
                # Usa tutte e 5 le carte comunitarie e le 2 in mano
                # NOTA: La funzione best_from_seven è un placeholder.
                # Per un gioco reale servirebbe una logica di valutazione mani corretta.
                score = best_from_seven(p.hole + self.community) 
                
                if score > best_score:
                    best_score = score
                    winners_for_pot = [p]
                elif score == best_score:
                    winners_for_pot.append(p)

            split_amount = pot_size // len(winners_for_pot)
            remainder = pot_size % len(winners_for_pot)
            
            for i, w in enumerate(winners_for_pot):
                amt = split_amount + (remainder if i == 0 else 0)
                w.chips += amt
                total_payout += amt
                
                existing_res = next((res for res in all_results if res['winner_name'] == w.name), None)
                if existing_res:
                    existing_res['amount'] += amt
                else:
                    all_results.append({
                        "winner_name": w.name,
                        "amount": amt,
                        # Assicurati che best_score[0] sia un indice valido per HAND_RANKS
                        "hand": HAND_RANKS[best_score[0]] if 0 <= best_score[0] < len(HAND_RANKS) else "Mano Sconosciuta"
                    })
                            
        self.pot = 0
        return all_results
