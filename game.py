#!/usr/bin/env python3
import random
import itertools
from typing import List, Optional, Dict, Tuple
from uuid import uuid4

# --- Costanti ---
RANKS = "23456789TJQKA"
SUITS = "SHDC"
RANK_VALUE = {r: i+2 for i, r in enumerate(RANKS)}  # 2-14 (A=14)
HAND_RANKS = [
    "High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush"
]

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
        """Ritorna la rappresentazione JSON della carta."""
        return {"rank": ("10" if self.rank == "T" else self.rank), "suit": self.suit, "str": repr(self)}

class Deck:
    """Rappresenta il mazzo di 52 carte e gestisce la pesca."""
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)

    def draw(self, n=1):
        """Pesca n carte dal mazzo."""
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
        """Ritorna lo stato pubblico del giocatore, rivelando le carte se `reveal=True`."""
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
    if 14 in vals: vals.append(1)  # Assi per scala bassa (A, 5, 4, 3, 2)
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
        self.turn_idx=-1 # Inizializza a -1 per non avere turni attivi
        self.started=False
        self.stage="waiting"
        self.last_raiser_idx=-1
        self.last_raise_amount=bb
        self.initial_bet_round_starter_idx = -1 
        self.is_hand_resolved = False 

    def add_player(self,name)->str:
        """Aggiunge un nuovo giocatore al tavolo."""
        if len(self.players)>=self.max_players: raise Exception("Room full")
        p=Player(name)
        self.players.append(p)
        return p.id

    def find_player(self,pid)->Optional[Player]:
        """Trova un giocatore tramite ID."""
        for p in self.players:
            if p.id==pid: return p
        return None

    def reset_for_new_hand(self):
        """Resetta lo stato del gioco per una nuova mano."""
        # Lo stato 'resolved' viene pulito qui per consentire una nuova mano.
        self.deck = None
        self.community = []
        self.pot = 0
        self.current_bet = 0
        self.turn_idx = -1 # Reset del turno
        self.started = False
        self.stage = "waiting"
        self.last_raiser_idx = -1
        self.last_raise_amount = self.bb
        self.initial_bet_round_starter_idx = -1
        self.is_hand_resolved = False 

    # --- Gestione pot e betting ---
    def flush_current_bets_to_pot(self):
        """Sposta le fiches scommesse in questo round nel piatto principale."""
        bets=sum(p.current_bet for p in self.players)
        if bets>0:
            self.pot+=bets
            for p in self.players: p.current_bet=0

    def start_hand(self)->Tuple[bool,str]:
        """Inizia una nuova mano: mischia, distribuisci e piazza i blinds."""
        # Se la mano precedente è risolta, esegue il reset.
        if self.is_hand_resolved:
            self.reset_for_new_hand()
            
        if len(self.players)<2: return False,"Serve almeno 2 giocatori"
        active=[p for p in self.players if p.chips>0]
        if len(active)<2: return False,"Non ci sono abbastanza giocatori con fiches"
        self.players=active
        
        # Inizializzazione della mano
        for p in self.players:
            p.hole=[]
            p.in_hand=True
            p.current_bet=0
            p.all_in=False
            p.total_contribution = 0 
            
        # Avanza il dealer (sulla nuova lista di giocatori attivi)
        if self.started:
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
            
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
        self.initial_bet_round_starter_idx = self.turn_idx

        return True,"Mano iniziata"

    # --- Stato pubblico ---
    def public_state(self,player_id)->Dict:
        """Ritorna lo stato del gioco per un giocatore specifico."""
        players_public=[]
        for p in self.players:
            # Le carte sono rivelate al giocatore attuale O se la fase è "showdown"
            reveal=(p.id==player_
