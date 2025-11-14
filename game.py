#!/usr/bin/env python3
import random
import itertools
from typing import List, Optional, Dict, Tuple
from uuid import uuid4

# --- Costanti ---
RANKS = "23456789TJQKA"
SUITS = "SHDC"
RANK_VALUE = {r: i+2 for i, r in enumerate(RANKS)}  # 2-14 (A=14)
HAND_RANKS = [
    "High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush"
]

# --- Utility ---
def normalize_rank(r: str) -> str:
    r = str(r).upper()
    if r == "10":
        return "T"
    return r

# --- Classi ---
class Card:
    """Rappresenta una singola carta."""
    def __init__(self, rank, suit):
        rank = normalize_rank(rank)
        if rank not in RANKS:
            raise ValueError(f"Rank non valido: {rank}")
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUE[rank]

    def __repr__(self):
        rank_str = "10" if self.rank == "T" else self.rank
        return f"{rank_str}{self.suit}"

    def to_dict(self):
        return {"rank": ("10" if self.rank == "T" else self.rank), "suit": self.suit, "str": repr(self)}

class Deck:
    """Rappresenta il mazzo di 52 carte e gestisce la pesca."""
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)

    def draw(self, n=1):
        drawn = self.cards[:n]
        self.cards = self.cards[n:]
        return drawn

class Player:
    """Rappresenta un giocatore al tavolo."""
    def __init__(self, name):
        self.id = str(uuid4())[:8]
        self.name = name
        self.chips = 1000
        self.hole: List[Card] = []
        self.in_hand = True
        self.current_bet = 0
        self.all_in = False
        self.total_contribution = 0 

    def to_public(self, reveal=False):
        return {
            "id": self.id,
            "name": self.name,
            "chips": self.chips,
            "in_hand": self.in_hand,
            "current_bet": self.current_bet,
            "all_in": self.all_in,
            "total_contribution": self.total_contribution,
            "hole": [repr(c) for c in self.hole] if reveal else (len(self.hole) * ["XX"])
        }

# --- Funzioni Texas Hold'em per l'Evaluation della Mano ---
def is_straight(values):
    """Controlla se i valori (già estratti e ordinati) formano una scala."""
    vals = sorted(set(values), reverse=True)
    if 14 in vals: vals.append(1)  # A low straight (A, 5, 4, 3, 2)
    for i in range(len(vals)-4):
        window = vals[i:i+5]
        if len(window)==5 and all(window[j]-window[j+1]==1 for j in range(4)):
            return window[0] # Ritorna il valore della carta più alta nella scala
    return None

def evaluate_5cards(cards: List[Card]):
    """Valuta il punteggio di una mano di 5 carte. Ritorna (rank_idx, kicker_tuple)."""
    values = sorted((c.value for c in cards), reverse=True)
    counts = {}
    for v in values: counts[v] = counts.get(v,0)+1
    by_count_then_value = sorted(counts.items(), key=lambda kv:(-kv[1],-kv[0]))
    
    # Straight Flush / Flush check helper
    suit_counts={}
    for c in cards: suit_counts.setdefault(c.suit,[]).append(c.value)

    # 8. Straight Flush
    for s,vals in suit_counts.items():
        if len(vals)>=5:
            fh=is_straight(sorted(vals,reverse=True))
            if fh: return (8,(fh,))
            
    # 7. Four of a Kind
    if by_count_then_value[0][1]==4:
        four=by_count_then_value[0][0]
        kicker=max(v for v in values if v!=four)
        return (7,(four,kicker))
        
    # 6. Full House
    if by_count_then_value[0][1]==3 and len(by_count_then_value)>1 and by_count_then_value[1][1]>=2:
        return (6,(by_count_then_value[0][0],by_count_then_value[1][0]))
        
    # 5. Flush
    for s in SUITS:
        suited=sorted([c.value for c in cards if c.suit==s],reverse=True)
        if len(suited)>=5: return (5,tuple(suited[:5]))
        
    # 4. Straight
    straight_high=is_straight(values)
    if straight_high: return (4,(straight_high,))
    
    # 3. Three of a Kind
    if by_count_then_value[0][1]==3:
        three=by_count_then_value[0][0]
        kickers=[v for v in values if v!=three][:2]
        return (3,(three,)+tuple(kickers))
        
    # 2. Two Pair
    if by_count_then_value[0][1]==2 and len(by_count_then_value)>1 and by_count_then_value[1][1]==2:
        hp=by_count_then_value[0][0]; lp=by_count_then_value[1][0]
        kicker=[v for v in values if v not in [hp, lp]][0]
        return (2,(hp,lp,kicker))
        
    # 1. One Pair
    if by_count_then_value[0][1]==2:
        pair=by_count_then_value[0][0]
        kickers=[v for v in values if v!=pair][:3]
        return (1,(pair,)+tuple(kickers))
        
    # 0. High Card
    return (0,tuple(values[:5]))

def best_from_seven(seven):
    """Trova la migliore mano di 5 carte da 7 carte totali."""
    best=(-1,())
    for combo in itertools.combinations(seven,5):
        score=evaluate_5cards(list(combo))
        if score>best: best=score
    return best

# --- Classe Game ---
class Game:
    """Gestisce lo stato e la logica del gioco Texas Hold'em."""
    def __init__(self,max_players=4,sb=10,bb=20):
        self.players: List[Player]=[]
        self.max_players=max_players
        self.sb=sb
        self.bb=bb
        self.deck: Optional[Deck]=None
        self.community: List[Card]=[]
        self.pot=0
        self.dealer_idx=0
        self.current_bet=0
        self.turn_idx=0
        self.started=False
        self.stage="waiting"
        self.last_raiser_idx=-1
        self.last_raise_amount=bb
        self.initial_bet_round_starter_idx = -1 # Indice del giocatore che ha iniziato il round (per i check)

    def add_player(self,name)->str:
        if len(self.players)>=self.max_players: raise Exception("Room full")
        p=Player(name)
        self.players.append(p)
        return p.id

    def find_player(self,pid)->Optional[Player]:
        for p in self.players:
            if p.id==pid: return p
        return None

    # --- Gestione pot e betting ---
    def flush_current_bets_to_pot(self):
        """Sposta le fiches scommesse in questo round nel piatto principale."""
        bets=sum(p.current_bet for p in self.players)
        if bets>0:
            self.pot+=bets
            for p in self.players: p.current_bet=0

    def start_hand(self)->Tuple[bool,str]:
        """Inizia una nuova mano: mischia, distribuisci e piazza i blinds."""
        if len(self.players)<2: return False,"Serve almeno 2 giocatori"
        active=[p for p in self.players if p.chips>0]
        if len(active)<2: return False,"Non ci sono abbastanza giocatori con fiches"
        self.players=active
        for p in self.players:
            p.hole=[]
            p.in_hand=True
            p.current_bet=0
            p.all_in=False
            p.total_contribution = 0 
            
        self.deck=Deck()
        self.community=[]
        self.pot=0
        self.current_bet=0
        self.started=True
        self.stage="preflop"
        self.last_raiser_idx=-1
        self.last_raise_amount=self.bb
        
        # Distribuzione carte
        for _ in range(2):
            for p in self.players: 
                if self.deck.cards: p.hole.append(self.deck.draw(1)[0])
        
        # Blinds
        self.dealer_idx=self.dealer_idx%len(self.players)
        sb_idx=(self.dealer_idx+1)%len(self.players)
        bb_idx=(self.dealer_idx+2)%len(self.players)
        
        # Small Blind
        sb_player=self.players[sb_idx]
        sb_amt=min(self.sb,sb_player.chips)
        sb_player.chips-=sb_amt; sb_player.current_bet=sb_amt; sb_player.total_contribution+=sb_amt; sb_player.all_in=sb_player.chips==0

        # Big Blind
        bb_player=self.players[bb_idx]
        bb_amt=min(self.bb,bb_player.chips)
        bb_player.chips-=bb_amt; bb_player.current_bet=bb_amt; bb_player.total_contribution+=bb_amt; bb_player.all_in=bb_player.chips==0
        
        self.pot+=sb_amt+bb_amt
        self.current_bet=bb_amt
        
        # Primo a parlare pre-flop è UTG (dopo BB)
        self.turn_idx=(bb_idx+1)%len(self.players) 
        self.last_raiser_idx=bb_idx 
        
        # UTG è il primo a parlare.
        self.initial_bet_round_starter_idx = self.turn_idx

        return True,"Mano iniziata"

    # --- Stato pubblico ---
    def public_state(self,player_id)->Dict:
        """Ritorna lo stato del gioco per un giocatore specifico."""
        players_public=[]
        for p in self.players:
            reveal=(p.id==player_id) or self.stage=="showdown"
            players_public.append(p.to_public(reveal=reveal))
            
        turn_player = self.players[self.turn_idx] if self.players and self.started and self.stage!="showdown" and self.turn_idx!=-1 else None
        
        return {
            "players":players_public,
            "community":[c.to_dict() for c in self.community],
            "pot":self.pot,
            "stage":self.stage,
            "dealer_idx":self.dealer_idx,
            "current_bet":self.current_bet,
            "turn_id":turn_player.id if turn_player else None,
            "hand_started":self.started,
            "required_call": self.current_bet - (self.find_player(player_id).current_bet if self.find_player(player_id) else 0)
        }
        
    def get_next_player_in_hand_idx(self, current_idx: int) -> int:
        """Trova l'indice del prossimo giocatore (in senso orario) che è ancora in mano."""
        n = len(self.players)
        for i in range(1, n + 1):
            idx = (current_idx + i) % n
            if self.players[idx].in_hand:
                return idx
        return -1 # Non dovrebbe succedere se la mano è iniziata e non è finita

    # --- Logica Turno e Avanzamento (FIXED) ---

    def all_but_one_folded(self):
        """Controlla se tutti i giocatori tranne uno hanno foldato."""
        inplay=[p for p in self.players if p.in_hand]
        return len(inplay)<=1

    def is_betting_round_over(self):
        """Controlla se il giro di puntate è terminato."""
        
        # 1. Mano Terminata
        if self.all_but_one_folded(): return True
            
        active_in_hand = [p for p in self.players if p.in_hand and not p.all_in]
        # Se solo 1 o 0 giocatori non sono All-in, il round è chiuso.
        if len(active_in_hand) <= 1: return True

        # 2. Requisito di Match
        # Tutti i giocatori attivi (non all-in) devono aver matchato la puntata.
        all_active_matched_bet = all(p.current_bet == self.current_bet for p in active_in_hand)
        
        if not all_active_matched_bet: return False # Qualcuno deve ancora chiamare
        
        # A questo punto, tutti i giocatori attivi hanno puntato `self.current_bet`.
        
        # 3. Requisito di Ciclo Completo
        
        # A. Caso con Puntata (Preflop dopo BB, o Raise Postflop):
        if self.current_bet > 0:
            # Se tutti hanno matchato una puntata > 0, il round è finito.
            return True
        
        # B. Caso senza Puntata (Giro di Check Postflop):
        if self.current_bet == 0:
            # Il round è finito SOLO se il prossimo giocatore ad agire è l'iniziatore.
            # (Il ciclo è completo, tutti hanno checkato).
            next_player_idx = self.get_next_player_in_hand_idx(self.turn_idx)
            
            if next_player_idx == self.initial_bet_round_starter_idx:
                return True
            else:
                # Il round continua (il turno deve passare al giocatore successivo).
                return False
                
        return False
        
    def get_first_to_act_post_flop(self):
        """Trova l'indice del primo giocatore attivo dopo il flop (primo attivo dopo il dealer)."""
        n = len(self.players)
        start_pos = (self.dealer_idx + 1) % n
        
        for i in range(n):
            idx = (start_pos + i) % n
            p = self.players[idx]
            # Il primo a parlare è il primo in mano e non all-in dopo il dealer.
            if p.in_hand and not p.all_in:
                return idx
        return -1 

    def advance_stage(self) -> Optional[Tuple[bool, str]]:
        """Avanza alla fase successiva (Flop, Turn, River, Showdown)."""
        self.flush_current_bets_to_pot()
        
        if self.stage=="preflop":
            if self.deck: self.community.extend(self.deck.draw(3)); self.stage="flop"
        elif self.stage=="flop":
            if self.deck: self.community.extend(self.deck.draw(1)); self.stage="turn"
        elif self.stage=="turn":
            if self.deck: self.community.extend(self.deck.draw(1)); self.stage="river"
        elif self.stage=="river":
            self.stage="showdown"
        else: 
            self.stage="waiting"; self.started=False; return None 

        # Reset delle puntate per il nuovo round
        self.current_bet=0
        self.last_raiser_idx=-1
        self.last_raise_amount=self.bb
        
        if self.stage=="showdown":
            # La mano è finita, assegna i piatti
            results = self.collect_pots_and_award()
            return True, f"Showdown! Risultati: {results}"

        # Determina il primo giocatore ad agire post-flop (SB se attivo, altrimenti il primo dopo D)
        first_to_act_idx = self.get_first_to_act_post_flop()
        
        if first_to_act_idx == -1:
             # Nessuno attivo non all-in, si avanza forzatamente fino allo showdown
             if len(self.community) < 5:
                 while len(self.community) < 5:
                     if self.deck: self.community.extend(self.deck.draw(1))
                 self.stage = "showdown"
                 results = self.collect_pots_and_award()
                 return True, f"Showdown forzato! Risultati: {results}"
             else:
                 self.stage = "showdown"
                 results = self.collect_pots_and_award()
                 return True, f"Showdown! Risultati: {results}"

        self.turn_idx = first_to_act_idx
        self.initial_bet_round_starter_idx = first_to_act_idx
        return None # Ritorna None se l'avanzamento di fase è avvenuto con successo

    # --- Azioni giocatore ---
    def check_and_advance_stage_if_round_over(self, action_description):
        """Passa il turno al giocatore successivo O avanza di fase/termina la mano."""
        
        # 1. Caso Mano Terminata (Solo 1 in mano)
        if self.all_but_one_folded():
            self.flush_current_bets_to_pot()
            results=self.collect_pots_and_award()
            return True,f"{action_description}. Mano terminata. Risultati:{results}"

        # 2. Caso Round Terminati (tutti chiamati/checkati)
        if self.is_betting_round_over():
            # Avanza di fase e gestisci il risultato se Showdown
            result_tuple = self.advance_stage()
            if result_tuple:
                return result_tuple 
            else:
                return True, action_description + f". Avanzamento a {self.stage}"
        
        # 3. Caso Round Continua
        # Passa il turno al prossimo in mano (non foldato) in modo circolare.
        next_idx = self.get_next_player_in_hand_idx(self.turn_idx)
        
        if next_idx != -1:
            self.turn_idx = next_idx
            return True, action_description
        else:
            # Caso di errore, ma gestito in `all_but_one_folded`
            return False, "Errore logico nel passaggio del turno (nessun prossimo giocatore in mano trovato)."

    def player_action(self,player_id,action,amount=0)->Tuple[bool,str]:
        p=self.find_player(player_id)
        if not p: return False,"Player non trovato"
        if not p.in_hand: return False,"Hai già foldato"
        if not self.started: return False,"Mano non iniziata"
        if self.players[self.turn_idx].id!=player_id: return False,"Non è il tuo turno"
        if p.all_in: return False,"Sei All-in, non puoi agire"
        
        action=action.lower()
        to_call=self.current_bet-p.current_bet
        
        # --- FOLD ---
        if action=="fold":
            p.in_hand=False
            return self.check_and_advance_stage_if_round_over("Fold")
            
        # --- CHECK ---
        if action=="check":
            if to_call>0: return False,"Non puoi checkare se c'è da chiamare/puntare"
            
            # Se la puntata corrente è 0, check è legale e il turno passa
            return self.check_and_advance_stage_if_round_over("Check")
            
        # --- CALL ---
        if action=="call":
            if to_call<=0: return False,"Non c'è nulla da chiamare o da puntare"
            put=min(to_call,p.chips)
            
            p.chips-=put
            p.current_bet+=put
            p.total_contribution+=put 
            if p.chips==0: p.all_in=True
            
            return self.check_and_advance_stage_if_round_over(f"Call {put}")
            
        # --- RAISE ---
        if action=="raise":
            if amount<=0: return False,"Importo raise non valido"
            
            # Il raise minimo è la dimensione dell'ultima puntata/rilancio, o BB
            min_raise_required = self.last_raise_amount 
            
            # 'amount' è la PUNTATA TOTALE che il giocatore vuole raggiungere
            total_bet_to_be = amount 
            
            # Quanto il giocatore deve mettere in gioco ORA
            total_put = total_bet_to_be - p.current_bet
            
            if total_put < to_call:
                return False, f"La tua puntata totale ({total_bet_to_be}) non copre l'importo da chiamare ({self.current_bet})."

            # 1. Verifica la dimensione del raise
            new_raise_amount = total_bet_to_be - self.current_bet
            
            # Solo se non si è all-in
            if new_raise_amount < min_raise_required and total_put < p.chips:
                 return False, f"Raise troppo piccolo. Il rilancio deve essere almeno {min_raise_required} oltre la puntata corrente."
                 
            # 2. Gestione All-in (sempre permesso, anche se un mini-raise)
            if total_put >= p.chips:
                total_put = p.chips
                total_bet_to_be = p.current_bet + total_put
                # Se l'all-in non è nemmeno un Call, non è valido (gestito da to_call)
                # Un all-in che è meno di un full raise è un "mini-raise" ed è valido.
                
            # 3. Applicazione della puntata
            old_current_bet = self.current_bet
            p.chips-=total_put
            p.current_bet=total_bet_to_be
            p.total_contribution+=total_put 

            if p.chips==0: p.all_in=True
            
            # 4. Aggiornamento dello stato del round se c'è un RILANCIO effettivo
            if p.current_bet>old_current_bet:
                self.last_raise_amount=p.current_bet-old_current_bet
                self.current_bet=p.current_bet
                self.last_raiser_idx=self.turn_idx
            
            return self.check_and_advance_stage_if_round_over(f"Raise {total_put} (totale: {p.current_bet})")
            
        return False,"Azione non riconosciuta"

    # --- Distribuzione Vincite (Mantenuta la logica Side Pots) ---
    def collect_pots_and_award(self):
        """Calcola i side pots e distribuisce il piatto totale."""
        inplay_with_contribution=[p for p in self.players if p.total_contribution>0]
        all_results = []
        
        if not inplay_with_contribution:
            self.started = False
            self.stage = "waiting"
            return [{"winner_name": "Nessuno", "amount": 0, "hand": "No Contributi"}]

        # Se è rimasto un solo giocatore non foldato (anche se è andato all-in), prende tutto
        inplay_no_fold = [p for p in self.players if p.in_hand]
        if len(inplay_no_fold) == 1:
            winner = inplay_no_fold[0]
            amt = sum(p.total_contribution for p in self.players)
            winner.chips += amt
            self.pot = 0
            self.started = False
            self.stage = "waiting"
            return [{"winner_name": winner.name, "amount": amt, "hand": "Unico Rimasto"}]


        # 1. Calcola i cap (livelli di contribuzione unici)
        contribution_caps = sorted(list(set(p.total_contribution for p in inplay_with_contribution)))
        
        pots = []
        previous_cap = 0
        
        # 2. Crea i pots (dal più piccolo al più grande)
        for cap in contribution_caps:
            slice_amount = cap - previous_cap
            if slice_amount > 0:
                # Giocatori eleggibili: hanno contribuito almeno fino a questo cap
                eligible_players = [p for p in inplay_with_contribution if p.total_contribution >= cap]
                
                # Dimensione del pot: slice_amount * numero di giocatori eleggibili
                pot_size = slice_amount * len(eligible_players)
                
                pots.append({
                    "size": pot_size,
                    "eligible": [p for p in eligible_players],
                    "cap": cap
                })
            previous_cap = cap
            
        # 3. Assegna i pot (dal più piccolo/principale al side pot più grande)
        # Il pot totale è già calcolato dai singoli contributi in 'pots'
        
        for pot in pots:
            # Solo i giocatori IN MANO (non foldato) sono eleggibili per la vincita
            eligible_in_hand = [p for p in pot["eligible"] if p.in_hand]
            
            if not eligible_in_hand:
                continue

            pot_size = pot["size"]
            
            # 4. Determina i Vincitori per questo Pot
            best_score = (-1, ())
            winners_for_pot = []
            
            for p in eligible_in_hand:
                score = best_from_seven(p.hole + self.community)
                
                if score > best_score:
                    best_score = score
                    winners_for_pot = [p]
                elif score == best_score:
                    winners_for_pot.append(p)

            # 5. Distribuisci la vincita
            split_amount = pot_size // len(winners_for_pot)
            remainder = pot_size % len(winners_for_pot)
            
            for i, w in enumerate(winners_for_pot):
                amt = split_amount + (remainder if i == 0 else 0)
                w.chips += amt
                
                # Aggiorna i risultati per la visualizzazione finale
                existing_res = next((res for res in all_results if res['winner_name'] == w.name), None)
                if existing_res:
                    existing_res['amount'] += amt
                else:
                    all_results.append({
                        "winner_name": w.name,
                        "amount": amt,
                        "hand": HAND_RANKS[best_score[0]]
                    })
                            
        self.pot = 0
        self.started = False
        self.stage = "waiting"
        
        return all_results
