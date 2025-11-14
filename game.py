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
        # AGGIUNTO: Contributo totale in fiches al piatto in questa mano. Essenziale per i side pots.
        self.total_contribution = 0 

    def to_public(self, reveal=False):
        return {
            "id": self.id,
            "name": self.name,
            "chips": self.chips,
            "in_hand": self.in_hand,
            "current_bet": self.current_bet,
            "all_in": self.all_in,
            "total_contribution": self.total_contribution, # Utile per debugging
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
        kickers=[v for v in values if v!=hp and v!=lp]
        # In 5-card evaluation, there's only one kicker left (5 cards total).
        kicker = [v for v in values if v not in [hp, lp]][0]
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
            p.total_contribution = 0 # RESET AGGIUNTO
            
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
                # Se il mazzo è vuoto, non pescare
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
        self.turn_idx=(bb_idx+1)%len(self.players)
        self.last_raiser_idx=bb_idx # BB è considerato il 'raiser' iniziale
        
        return True,"Mano iniziata"

    # --- Stato pubblico ---
    def public_state(self,player_id)->Dict:
        """Ritorna lo stato del gioco per un giocatore specifico."""
        players_public=[]
        for p in self.players:
            # Rivela le carte solo al giocatore stesso o durante lo showdown
            reveal=(p.id==player_id) or self.stage=="showdown"
            players_public.append(p.to_public(reveal=reveal))
            
        turn_player = self.players[self.turn_idx] if self.players and self.started and self.stage!="showdown" else None
        
        return {
            "players":players_public,
            "community":[c.to_dict() for c in self.community],
            "pot":self.pot,
            "stage":self.stage,
            "dealer_idx":self.dealer_idx,
            "current_bet":self.current_bet,
            "turn_id":turn_player.id if turn_player else None,
            "hand_started":self.started
        }

    # --- Logica Turno e Avanzamento (FIXED) ---

    def find_next_player_to_act(self, start_idx: int) -> Optional[int]:
        """Trova il prossimo giocatore attivo che deve ancora agire (ovvero chiamare o foldare)."""
        n = len(self.players)
        for i in range(1, n + 1):
            idx = (start_idx + i) % n
            p = self.players[idx]
            
            # Un giocatore deve agire se:
            # 1. È ancora in mano (non ha foldato)
            # 2. Non è all-in
            # 3. La sua puntata corrente è inferiore alla puntata massima del round
            if p.in_hand and not p.all_in and p.current_bet < self.current_bet:
                return idx
        
        # Se il ciclo si completa senza trovare nessuno, il round è finito (None)
        return None

    def all_but_one_folded(self):
        """Controlla se tutti i giocatori tranne uno hanno foldato."""
        inplay=[p for p in self.players if p.in_hand]
        return len(inplay)<=1

    def is_betting_round_over(self):
        """Controlla se il giro di puntate è terminato."""
        
        # Se c'è solo un giocatore in mano, il round (e la mano) è finito.
        if self.all_but_one_folded():
            return True
            
        # Il round è terminato se non c'è più nessuno che deve agire.
        # Chiamiamo find_next_player_to_act partendo dalla posizione attuale.
        # Se find_next_player_to_act trova qualcuno, allora il round NON è finito.
        return self.find_next_player_to_act(self.turn_idx) is None


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
            # D'ora in poi, dopo lo showdown, lo stato diventa "waiting"
            self.stage="waiting"; self.started=False; return None 

        # Reset delle puntate per il nuovo round
        self.current_bet=0
        self.last_raiser_idx=-1
        self.last_raise_amount=self.bb
        
        if self.stage=="showdown":
            # La mano è finita, assegna i piatti
            results = self.collect_pots_and_award()
            return True, f"Showdown! Risultati: {results}"

        # Determina il primo giocatore ad agire post-flop (il primo attivo dopo il dealer)
        n = len(self.players)
        start_pos = (self.dealer_idx + 1) % n
        
        first_to_act_idx = start_pos
        for i in range(n):
            idx = (start_pos + i) % n
            p = self.players[idx]
            if p.in_hand and not p.all_in:
                first_to_act_idx = idx
                break
        
        self.turn_idx = first_to_act_idx
        return None # Ritorna None se l'avanzamento di fase è avvenuto con successo

    # --- Azioni giocatore (FIXED) ---
    def player_action(self,player_id,action,amount=0)->Tuple[bool,str]:
        p=self.find_player(player_id)
        if not p: return False,"Player non trovato"
        if not p.in_hand: return False,"Hai già foldato"
        if not self.started: return False,"Mano non iniziata"
        if self.players[self.turn_idx].id!=player_id: return False,"Non è il tuo turno"
        if p.all_in: return False,"Sei All-in, non puoi agire (tranne forzatamente nel Big Blind)"
        
        action=action.lower()
        to_call=self.current_bet-p.current_bet
        
        # --- Helper per l'avanzamento del turno ---
        def proceed_turn(self, action_description):
            # Controlla se il round di puntate è finito dopo questa azione
            if self.is_betting_round_over():
                # Avanza di fase e ottieni il risultato se la mano finisce (Showdown)
                result_tuple = self.advance_stage()
                if result_tuple:
                    return result_tuple # Ritorna il risultato dello Showdown
            else:
                # Trova il prossimo giocatore che DEVE agire
                next_idx = self.find_next_player_to_act(self.turn_idx)
                if next_idx is not None:
                    self.turn_idx = next_idx
                else:
                    # Caso teorico: tutti hanno chiamato/checkato, ma la logica precedente dovrebbe catturarlo
                    self.advance_stage() 
            return True, action_description

        # --- FOLD ---
        if action=="fold":
            p.in_hand=False
            if self.all_but_one_folded():
                self.flush_current_bets_to_pot()
                results=self.collect_pots_and_award()
                return True,f"Hai foldato. Mano terminata. Risultati:{results}"
            
            return proceed_turn(self, "Fold")
            
        # --- CHECK ---
        if action=="check":
            if to_call>0: return False,"Non puoi checkare se c'è da chiamare"
            return proceed_turn(self, "Check")
            
        # --- CALL ---
        if action=="call":
            if to_call<=0: return False,"Non c'è nulla da chiamare"
            put=min(to_call,p.chips)
            p.chips-=put
            p.current_bet+=put
            p.total_contribution+=put # AGGIORNATO: Traccia contributo totale
            if p.chips==0: p.all_in=True
            
            return proceed_turn(self, f"Call {put}")
            
        # --- RAISE ---
        if action=="raise":
            if amount<=0: return False,"Importo raise non valido"
            
            min_raise=self.last_raise_amount if self.last_raiser_idx!=-1 else self.bb
            
            # Quanto si deve mettere in totale per chiamare + rilanciare (minimo)
            total_needed_to_be_min_raise = self.current_bet + min_raise
            
            # Se l'importo fornito è il totale del nuovo bet, calcoliamo la differenza.
            # Qui assumiamo che 'amount' sia l'ammontare TOTALE che il giocatore vuole puntare (il nuovo current_bet).
            
            # Calcoliamo quanto deve puntare il giocatore in totale
            total_bet_to_be = amount # Si assume che 'amount' sia il *totale* della puntata
            
            # Il giocatore deve mettere in gioco: total_bet_to_be - p.current_bet
            total_put = total_bet_to_be - p.current_bet
            
            if total_put < to_call:
                return False, f"La tua puntata totale ({total_bet_to_be}) non copre l'importo da chiamare ({self.current_bet})."

            if total_put > p.chips:
                # All-in
                total_put = p.chips
                total_bet_to_be = p.current_bet + total_put
            
            # Nuova puntata totale del giocatore
            new_current_bet = p.current_bet + total_put
            
            # Controllo Raise minimo (solo se non è un all-in per meno del min_raise)
            is_full_raise = (new_current_bet - self.current_bet) >= min_raise
            is_all_in_and_raises_previous_bet = (total_put == p.chips) and (new_current_bet > self.current_bet)
            
            if new_current_bet > self.current_bet and not is_full_raise and not is_all_in_and_raises_previous_bet:
                 return False, f"Raise troppo piccolo. La puntata totale deve essere almeno {total_needed_to_be_min_raise}."
            
            # Applicazione della puntata
            old_current_bet = self.current_bet
            p.chips-=total_put
            p.current_bet=new_current_bet
            p.total_contribution+=total_put # AGGIORNATO: Traccia contributo totale

            if p.chips==0: p.all_in=True
            
            # Aggiornamento dello stato del round se c'è un RILANCIO effettivo
            if p.current_bet>old_current_bet:
                self.last_raise_amount=p.current_bet-old_current_bet
                self.current_bet=p.current_bet
                self.last_raiser_idx=self.turn_idx
            
            return proceed_turn(self, f"Raise {total_put} (totale: {p.current_bet})")
            
        return False,"Azione non riconosciuta"

    # --- Distribuzione Vincite (FIXED and implemented Side Pots) ---
    def collect_pots_and_award(self):
        """Calcola i side pots e distribuisce il piatto totale. (FIXED)"""
        inplay_with_contribution=[p for p in self.players if p.total_contribution>0]
        all_results = []
        
        if not inplay_with_contribution:
            self.started = False
            self.stage = "waiting"
            return [{"winner_name": "Nessuno", "amount": 0, "hand": "No Contributi"}]

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
            
        money_remaining_to_distribute = self.pot

        # 3. Assegna i pot (dal più piccolo/principale al side pot più grande)
        for pot in pots:
            if money_remaining_to_distribute == 0:
                break
                
            # Solo i giocatori IN MANO (non foldato) sono eleggibili per la vincita
            eligible_in_hand = [p for p in pot["eligible"] if p.in_hand]
            
            if not eligible_in_hand:
                # Nessuno eleggibile per vincere questo pot (tutti foldati) -> il denaro torna nel pot principale per essere riassegnato
                continue

            # La dimensione del pot è limitata dal denaro rimasto
            pot_size = min(pot["size"], money_remaining_to_distribute)
            
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
                money_remaining_to_distribute -= amt
                
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
