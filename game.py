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
            reveal=(p.id==player_id) or self.stage=="showdown"
            players_public.append(p.to_public(reveal=reveal))
            
        turn_name = None 

        # Controlliamo esplicitamente l'indice e lo stato
        if (self.players and self.started and self.stage!="showdown" and 
            0 <= self.turn_idx < len(self.players)):
            
            turn_player = self.players[self.turn_idx]
            # turn_id rimosso per evitare confusioni nel client
            turn_name = turn_player.name
            
        return {
            "players":players_public,
            "community":[c.to_dict() for c in self.community],
            "pot":self.pot,
            "stage":self.stage,
            "dealer_idx":self.dealer_idx,
            "current_bet":self.current_bet,
            # Campo corretto da usare nel client:
            "turn_name":turn_name, 
            "hand_started":self.started,
            "required_call": self.current_bet - (self.find_player(player_id).current_bet if self.find_player(player_id) else 0)
        }
        
    def get_next_player_in_hand_idx(self, current_idx: int) -> int:
        """Trova l'indice del prossimo giocatore (in senso orario) che è ancora in mano."""
        n = len(self.players)
        for i in range(1, n + 1):
            idx = (current_idx + i) % n
            p = self.players[idx]
            # Deve essere in mano E non All-in se ha ancora da agire
            if p.in_hand and not (p.all_in and p.current_bet == self.current_bet):
                return idx
        return -1 

    # --- Logica Turno e Avanzamento ---

    def all_but_one_folded(self):
        """Controlla se tutti i giocatori tranne uno hanno foldato."""
        inplay=[p for p in self.players if p.in_hand]
        return len(inplay)<=1

    def is_betting_round_over(self):
        """Controlla se il giro di puntate è terminato."""
        
        if self.all_but_one_folded(): return True
            
        active_in_hand = [p for p in self.players if p.in_hand]
        
        # Giocatori che DEVONO agire (non foldati e non All-in che hanno già matchato)
        must_act = [p for p in active_in_hand if not (p.all_in and p.current_bet == self.current_bet)]
        
        if not must_act:
            # Tutti gli attivi sono All-in o hanno matchato All-in. Round finito.
            return True
        
        all_active_matched_bet = all(p.current_bet == self.current_bet for p in must_act)
        
        if not all_active_matched_bet: return False 
        
        # Requisito di Ciclo Completo
        if self.current_bet == 0 and self.stage != "preflop":
            next_idx = self.get_next_player_in_hand_idx(self.turn_idx)
            # Se il prossimo è l'iniziatore (il ciclo è completo)
            if next_idx == self.initial_bet_round_starter_idx:
                return True
            # Se nessuno deve agire (tutti check), e siamo tornati al first_to_act_post_flop, è finita.
            elif next_idx == -1 and self.turn_idx == self.initial_bet_round_starter_idx:
                 return True
            else:
                return False
                
        # Se c'è stata una puntata (current_bet > 0) e tutti hanno matchato, il round è finito.
        return True
        
    def get_first_to_act_post_flop(self):
        """Trova l'indice del primo giocatore attivo dopo il flop (primo attivo dopo il dealer)."""
        n = len(self.players)
        start_pos = (self.dealer_idx + 1) % n
        
        for i in range(n):
            idx = (start_pos + i) % n
            p = self.players[idx]
            # Primo a parlare: in mano e non all-in
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
        
        # Reset delle puntate per il nuovo round
        self.current_bet=0
        self.last_raiser_idx=-1
        self.last_raise_amount=self.bb
        
        if self.stage=="showdown":
            # La mano è finita, assegna i piatti e imposta il flag risolto
            results = self.collect_pots_and_award()
            self.is_hand_resolved = True 
            # Non impostiamo turn_idx a -1 qui, lo facciamo nel chiamante (check_and_advance_stage_if_round_over)
            return True, f"Showdown! Risultati: {results}"

        # Determina il primo giocatore ad agire post-flop
        first_to_act_idx = self.get_first_to_act_post_flop()
        
        if first_to_act_idx == -1:
             # Nessuno attivo non all-in, avanza forzatamente le carte e imposta showdown
             while len(self.community) < 5:
                 if self.deck: self.community.extend(self.deck.draw(1))
             self.stage = "showdown"
             results = self.collect_pots_and_award()
             self.is_hand_resolved = True
             return True, f"Showdown forzato! Risultati: {results}"

        self.turn_idx = first_to_act_idx
        self.initial_bet_round_starter_idx = first_to_act_idx
        return None 

    # --- Azioni giocatore ---
    def check_and_advance_stage_if_round_over(self, action_description: str):
        """Passa il turno al giocatore successivo O avanza di fase/termina la mano."""
        
        # 1. Caso Mano Terminata (Solo 1 in mano)
        if self.all_but_one_folded():
            self.stage = "showdown" 
            self.flush_current_bets_to_pot()
            results=self.collect_pots_and_award()
            self.is_hand_resolved = True 
            self.turn_idx = -1 # <--- FIX: Resetta il turno quando la mano è risolta
            return True,f"{action_description}. Mano terminata per fold. Risultati:{results}"

        # 2. Caso Round Terminati (tutti chiamati/checkati)
        if self.is_betting_round_over():
            # Avanza di fase e gestisci il risultato se Showdown
            result_tuple = self.advance_stage()
            if result_tuple:
                # Se la mano è andata a showdown, resettiamo l'indice del turno
                if self.stage == "showdown":
                    self.turn_idx = -1 # <--- FIX: Resetta il turno quando la mano è risolta
                return result_tuple 
            else:
                return True, action_description + f". Avanzamento a {self.stage}"
        
        # 3. Caso Round Continua
        next_idx = self.get_next_player_in_hand_idx(self.turn_idx)
        
        if next_idx != -1:
            self.turn_idx = next_idx
            return True, action_description
        else:
            # Fallback (dovrebbe essere gestito da is_betting_round_over/advance_stage)
            return self.advance_stage() or (True, action_description + ". Avanzamento di fase forzato.")

    def player_action(self,player_id,action,amount=0)->Tuple[bool,str]:
        p=self.find_player(player_id)
        if not p: return False,"Player non trovato"
        if not p.in_hand: return False,"Hai già foldato"
        if not self.started: return False,"Mano non iniziata"
        if self.stage=="showdown" or self.is_hand_resolved: return False,"La mano è finita (showdown), avviare la prossima."
        
        # Controllo indice valido prima di accedere a self.players
        if not (0 <= self.turn_idx < len(self.players)):
            return False,"Errore di stato: Turno non valido (indice fuori limite)"
            
        if self.players[self.turn_idx].id!=player_id: return False,"Non è il tuo turno"
        if p.all_in: return False,"Sei All-in, non puoi agire"
        
        action=action.lower()
        to_call=self.current_bet-p.current_bet
        
        # Ottieni il nome del giocatore per la descrizione
        player_name = p.name
        
        # --- FOLD ---
        if action=="fold":
            p.in_hand=False
            return self.check_and_advance_stage_if_round_over(f"**{player_name}** folda")
            
        # --- CHECK ---
        if action=="check":
            if to_call>0: return False,"Non puoi checkare se c'è da chiamare/puntare"
            return self.check_and_advance_stage_if_round_over(f"**{player_name}** checka")
            
        # --- CALL ---
        if action=="call":
            if to_call<=0 and self.current_bet>0: return False,"Non c'è nulla da chiamare"
            if to_call<0: to_call=0 # Assicura che to_call sia almeno 0 se current_bet era 0
            
            put=min(to_call,p.chips)
            
            p.chips-=put
            p.current_bet+=put
            p.total_contribution+=put 
            if p.chips==0: p.all_in=True
            
            return self.check_and_advance_stage_if_round_over(f"**{player_name}** chiama {put} fiches")
            
        # --- RAISE ---
        if action=="raise":
            if amount<=0: return False,"Importo raise non valido"
            
            min_raise_required = self.last_raise_amount 
            total_bet_to_be = amount 
            total_put = total_bet_to_be - p.current_bet
            
            if total_put < to_call:
                return False, f"La tua puntata totale ({total_bet_to_be}) non copre l'importo da chiamare ({self.current_bet})."

            new_raise_amount = total_bet_to_be - self.current_bet
            
            # Se non è All-in, deve rispettare il min_raise
            if new_raise_amount < min_raise_required and total_put < p.chips:
                 return False, f"Raise troppo piccolo. Il rilancio deve essere almeno {min_raise_required} oltre la puntata corrente ({self.current_bet})."
                 
            # Gestione All-in
            if total_put >= p.chips:
                total_put = p.chips
                total_bet_to_be = p.current_bet + total_put
                
            old_current_bet = self.current_bet
            p.chips-=total_put
            p.current_bet=total_bet_to_be
            p.total_contribution+=total_put 

            if p.chips==0: p.all_in=True
            
            # Aggiornamento puntata corrente e raiser solo se c'è stato un vero raise
            if p.current_bet>old_current_bet:
                # Il nuovo raise è la differenza tra la nuova puntata e la vecchia puntata massima
                self.last_raise_amount=p.current_bet-old_current_bet
                self.current_bet=p.current_bet
                self.last_raiser_idx=self.turn_idx
            
            return self.check_and_advance_stage_if_round_over(f"**{player_name}** rilancia di {total_put} (totale: {p.current_bet})")
            
        return False,"Azione non riconosciuta"

    # --- Distribuzione Vincite ---
    def collect_pots_and_award(self):
        """Calcola i side pots e distribuisce il piatto totale."""
        inplay_with_contribution=[p for p in self.players if p.total_contribution>0]
        all_results = []
        
        if not inplay_with_contribution:
            return [{"winner_name": "Nessuno", "amount": 0, "hand": "No Contributi"}]

        # Caso di vincita per fold (un solo giocatore in mano)
        inplay_no_fold = [p for p in self.players if p.in_hand]
        if len(inplay_no_fold) == 1:
            winner = inplay_no_fold[0]
            amt = sum(p.total_contribution for p in self.players)
            winner.chips += amt
            self.pot = 0
            return [{"winner_name": winner.name, "amount": amt, "hand": "Unico Rimasto"}]

        # Logica Side Pot...
        contribution_caps = sorted(list(set(p.total_contribution for p in inplay_with_contribution)))
        pots = []
        previous_cap = 0
        
        for cap in contribution_caps:
            slice_amount = cap - previous_cap
            if slice_amount > 0:
                eligible_players = [p for p in inplay_with_contribution if p.total_contribution >= cap]
                pot_size = slice_amount * len(eligible_players)
                pots.append({"size": pot_size, "eligible": [p for p in eligible_players], "cap": cap})
            previous_cap = cap
            
        for pot in pots:
            eligible_in_hand = [p for p in pot["eligible"] if p.in_hand]
            
            if not eligible_in_hand:
                continue

            pot_size = pot["size"]
            best_score = (-1, ())
            winners_for_pot = []
            
            for p in eligible_in_hand:
                # Usa tutte e 5 le carte comunitarie e le 2 in mano
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
        return all_results
