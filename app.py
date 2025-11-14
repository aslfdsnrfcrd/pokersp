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

# --- Classi di Base ---
class Card:
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
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
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

# --- Funzioni di valutazione Texas Hold'em ---
def is_straight(values):
    vals = sorted(set(values), reverse=True)
    if 14 in vals:
        vals.append(1)
    for i in range(len(vals) - 4):
        window = vals[i:i + 5]
        if len(window) == 5 and all(window[j] - window[j + 1] == 1 for j in range(4)):
            return window[0]
    return None

def evaluate_5cards(cards: List[Card]):
    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    by_count_then_value = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))

    # Straight Flush
    suit_counts = {}
    for c in cards:
        suit_counts.setdefault(c.suit, []).append(c.value)
    for s, vals in suit_counts.items():
        if len(vals) >= 5:
            fh = is_straight(sorted(vals, reverse=True))
            if fh:
                return (8, (fh,))

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
        suited = sorted([c.value for c in cards if c.suit == s], reverse=True)
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
        return (3, (three,) + tuple(kickers))

    # Two Pair
    if by_count_then_value[0][1] == 2 and len(by_count_then_value) > 1 and by_count_then_value[1][1] == 2:
        hp = by_count_then_value[0][0]; lp = by_count_then_value[1][0]
        kicker = max(v for v in values if v != hp and v != lp)
        return (2, (hp, lp, kicker))

    # One Pair
    if by_count_then_value[0][1] == 2:
        pair = by_count_then_value[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, (pair,) + tuple(kickers))

    # High Card
    return (0, tuple(values[:5]))

def best_from_seven(seven):
    best = (-1, ())
    for combo in itertools.combinations(seven, 5):
        score = evaluate_5cards(list(combo))
        if score > best:
            best = score
    return best

# --- Classe Game ---
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
        self.stage = "waiting"
        self.last_raiser_idx = -1
        self.last_raise_amount = bb

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

    # --- Gestione pot e betting ---
    def flush_current_bets_to_pot(self):
        bets = sum(p.current_bet for p in self.players)
        if bets > 0:
            self.pot += bets
            for p in self.players:
                p.current_bet = 0

    def start_hand(self) -> Tuple[bool, str]:
        if len(self.players) < 2:
            return False, "Serve almeno 2 giocatori"

        active_players = [p for p in self.players if p.chips > 0]
        if len(active_players) < 2:
            return False, "Non ci sono abbastanza giocatori con fiches."

        self.players = active_players
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
        self.last_raiser_idx = -1
        self.last_raise_amount = self.bb

        # Distribuzione carte
        for _ in range(2):
            for p in self.players:
                p.hole.append(self.deck.draw(1)[0])

        # Blinds
        self.dealer_idx = self.dealer_idx % len(self.players)
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
        self.turn_idx = (bb_idx + 1) % len(self.players)
        self.last_raiser_idx = bb_idx

        return True, "Mano iniziata"

    # --- Stato pubblico ---
    def public_state(self, player_id) -> Dict:
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

    # --- Azioni giocatore ---
    def player_action(self, player_id, action, amount=0) -> Tuple[bool, str]:
        p = self.find_player(player_id)
        if not p: return False, "Player non trovato"
        if not p.in_hand: return False, "Hai già foldato"
        if not self.started: return False, "Mano non iniziata"
        if self.players[self.turn_idx].id != player_id: return False, "Non è il tuo turno"
        if p.all_in: return False, "Sei All-in, non puoi agire"

        action = action.lower()
        to_call = self.current_bet - p.current_bet

        if action == "fold":
            p.in_hand = False
            if len([pl for pl in self.players if pl.in_hand]) == 1:
                self.flush_current_bets_to_pot()
                self.collect_pots_and_award()
            else:
                self.turn_idx = (self.turn_idx + 1) % len(self.players)
            return True, "Fold"

        if action == "check":
            if to_call > 0:
                return False, "Non puoi checkare se c'è da chiamare"
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.is_betting_round_over():
                self.advance_stage()
            return True, "Check"

        if action == "call":
            if to_call <= 0:
                return False, "Non c'è nulla da chiamare"
            put = min(to_call, p.chips)
            p.chips -= put
            p.current_bet += put
            if p.chips == 0: p.all_in = True
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.is_betting_round_over():
                self.advance_stage()
            return True, f"Call {put}"

        if action == "raise":
            if amount <= 0: return False, "Importo raise non valido"
            total_bet = to_call + amount
            if total_bet >= p.chips:
                total_bet = p.chips
                p.all_in = True
            p.chips -= total_bet
            p.current_bet += total_bet
            if p.current_bet > self.current_bet:
                self.last_raise_amount = p.current_bet - self.current_bet
                self.current_bet = p.current_bet
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.is_betting_round_over():
                self.advance_stage()
            return True, f"Raise {amount}"

        return False, "Azione non riconosciuta"

    def is_betting_round_over(self):
        active = [p for p in self.players if p.in_hand and not p.all_in]
        if not active: return True
        return all(p.current_bet == self.current_bet for p in active)

    def advance_stage(self):
        self.flush_current_bets_to_pot()
        if self.stage == "preflop": self.community.extend(self.deck.draw(3)); self.stage = "flop"
        elif self.stage == "flop": self.community.extend(self.deck.draw(1)); self.stage = "turn"
        elif self.stage == "turn": self.community.extend(self.deck.draw(1)); self.stage = "river"
        elif self.stage == "river": self.stage = "showdown"
        else: self.stage = "waiting"; self.started = False; return
        self.current_bet = 0
        self.last_raiser_idx = -1
        self.last_raise_amount = self.bb
        self.turn_idx = (self.dealer_idx + 1) % len(self.players)

    def collect_pots_and_award(self):
        inplay = [p for p in self.players if p.in_hand]
        if len(inplay) == 1:
            winner = inplay[0]
            winner.chips += self.pot
            self.pot = 0
            self.started = False
            self.stage = "waiting"
            return [{"winner_name": winner.name, "amount": winner.chips, "hand": "Unico Rimasto"}]

        best_score = None
        winners = []
        for p in inplay:
            score = best_from_seven(p.hole + self.community)
            if best_score is None or score > best_score:
                best_score = score
                winners = [(p, HAND_RANKS[score[0]])]
            elif score == best_score:
                winners.append((p, HAND_RANKS[score[0]]))
        split = self.pot // len(winners)
        remaining = self.pot % len(winners)
        results = []
        for i, (w, hand_type) in enumerate(winners):
            amt = split + (remaining if i==0 else 0)
            w.chips += amt
            results.append({"winner_name": w.name, "amount": amt, "hand": hand_type})
        self.pot = 0
        self.started = False
        self.stage = "waiting"
        return results
