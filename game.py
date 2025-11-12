#!/usr/bin/env python3
import random
import itertools
from typing import List, Optional, Dict, Tuple
from uuid import uuid4

RANKS = "23456789TJQKA"
SUITS = "SHDC"  # using letters for easier JSON
RANK_VALUE = {r: i+2 for i, r in enumerate(RANKS)}
HAND_RANKS = [
    "High Card","One Pair","Two Pair","Three of a Kind","Straight",
    "Flush","Full House","Four of a Kind","Straight Flush"
]

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
            "hole": [c.to_dict() for c in self.hole] if reveal else (len(self.hole) * ["XX"])
        }

# Simple evaluator used only for showdown — same idea as CLI version but simplified
def is_straight(values):
    vals = sorted(set(values), reverse=True)
    if 14 in vals:
        vals.append(1)
    for i in range(len(vals)-4):
        window = vals[i:i+5]
        if all(window[j]-window[j+1]==1 for j in range(4)):
            return window[0]
    return None

def evaluate_5cards(cards: List[Card]):
    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    counts = {}
    for v in values:
        counts[v] = counts.get(v,0)+1
    by_count_then_value = sorted(counts.items(), key=lambda kv:(-kv[1], -kv[0]))
    # straight flush
    suit_counts = {}
    for c in cards:
        suit_counts.setdefault(c.suit, []).append(c.value)
    for s, vals in suit_counts.items():
        if len(vals) >= 5:
            fh = is_straight(sorted(vals, reverse=True))
            if fh:
                return (8, (fh,))
    # four, fullhouse, flush...
    if by_count_then_value[0][1] == 4:
        four = by_count_then_value[0][0]
        kicker = max(v for v in values if v != four)
        return (7, (four, kicker))
    if by_count_then_value[0][1] == 3 and len(by_count_then_value) > 1 and by_count_then_value[1][1] >= 2:
        return (6, (by_count_then_value[0][0], by_count_then_value[1][0]))
    for s in SUITS:
        suited = sorted([c.value for c in cards if c.suit==s], reverse=True)
        if len(suited) >= 5:
            return (5, tuple(suited[:5]))
    straight_high = is_straight(values)
    if straight_high:
        return (4, (straight_high,))
    if by_count_then_value[0][1] == 3:
        three = by_count_then_value[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, (three,)+tuple(kickers))
    if by_count_then_value[0][1] == 2 and len(by_count_then_value) > 1 and by_count_then_value[1][1] == 2:
        hp = by_count_then_value[0][0]; lp = by_count_then_value[1][0]
        kicker = max(v for v in values if v != hp and v != lp)
        return (2, (hp, lp, kicker))
    if by_count_then_value[0][1] == 2:
        pair = by_count_then_value[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, (pair,)+tuple(kickers))
    return (0, tuple(values[:5]))

def best_from_seven(seven):
    best = (-1, ())
    for combo in itertools.combinations(seven, 5):
        score = evaluate_5cards(list(combo))
        if score > best:
            best = score
    return best

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
        self.last_action_time = 0

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
        sb_idx = (self.dealer_idx + 1) % len(self.players)
        bb_idx = (self.dealer_idx + 2) % len(self.players)
        sb_player = self.players[sb_idx]
        bb_player = self.players[bb_idx]
        sb_amt = min(self.sb, sb_player.chips)
        bb_amt = min(self.bb, bb_player.chips)
        sb_player.chips -= sb_amt; sb_player.current_bet = sb_amt
        bb_player.chips -= bb_amt; bb_player.current_bet = bb_amt
        self.pot += sb_amt + bb_amt
        self.current_bet = bb_amt
        # first to act is player after BB
        self.turn_idx = (bb_idx + 1) % len(self.players)
        self.last_action_time = 0
        return True, "Mano iniziata"

    def advance_stage(self):
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
        # reset current bets for next round
        for p in self.players:
            p.current_bet = 0
        self.current_bet = 0
        # next to act is player after dealer
        self.turn_idx = (self.dealer_idx + 1) % len(self.players)

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
            "turn_id": self.players[self.turn_idx].id if self.players else None,
            "hand_started": self.started
        }

    def next_active_idx(self, start):
        n = len(self.players)
        for i in range(1, n+1):
            idx = (start + i) % n
            p = self.players[idx]
            if p.in_hand and p.chips > 0:
                return idx
        return None

    def all_but_one_folded(self):
        inplay = [p for p in self.players if p.in_hand]
        return len(inplay) <= 1

    def collect_pots_and_award(self):
        # simplified: award whole pot to single remaining player or split equally among best hands
        inplay = [p for p in self.players if p.in_hand]
        if len(inplay) == 1:
            winner = inplay[0]
            winner.chips += self.pot
            self.pot = 0
            return [{"winner": winner.id, "amount": winner.chips}]
        # showdown evaluation
        results = []
        best_score = None
        winners = []
        for p in inplay:
            seven = p.hole + self.community
            score = best_from_seven(seven)
            if best_score is None or score > best_score:
                best_score = score
                winners = [p]
            elif score == best_score:
                winners.append(p)
        split = self.pot // len(winners)
        for w in winners:
            w.chips += split
        self.pot = 0
        return [{"winner": w.id, "amount": split} for w in winners]

    def player_action(self, player_id, action, amount=0) -> Tuple[bool, str]:
        p = self.find_player(player_id)
        if not p:
            return False, "Player non trovato"
        if not p.in_hand:
            return False, "Hai già foldato"
        if not self.started:
            return False, "Mano non iniziata"
        if self.players[self.turn_idx].id != player_id:
            return False, "Non è il tuo turno"
        action = action.lower()
        # fold
        if action == "fold":
            p.in_hand = False
            # advance turn
            if self.all_but_one_folded():
                # award pot
                self.collect_pots_and_award()
                self.started = False
                self.stage = "waiting"
                self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
                return True, "Hai foldato. Altri hanno foldato, mano terminata."
            nxt = self.next_active_idx(self.turn_idx)
            if nxt is not None:
                self.turn_idx = nxt
            return True, "Fold"
        # check
        to_call = self.current_bet - p.current_bet
        if action == "check":
            if to_call > 0:
                return False, "Non puoi checkare se c'è da chiamare"
            # advance
            nxt = self.next_active_idx(self.turn_idx)
            if nxt is None or nxt == self.turn_idx:
                # betting round over -> next stage
                self.advance_stage()
            else:
                self.turn_idx = nxt
            return True, "Check"
        if action == "call":
            if to_call <= 0:
                return False, "Non c'è nulla da chiamare"
            put = min(to_call, p.chips)
            p.chips -= put
            p.current_bet += put
            self.pot += put
            if p.chips == 0:
                p.all_in = True
            # advance
            nxt = self.next_active_idx(self.turn_idx)
            if nxt is None or nxt == self.turn_idx:
                self.advance_stage()
            else:
                self.turn_idx = nxt
            return True, "Call"
        if action == "raise":
            if amount <= 0:
                return False, "Specifica un importo valido per il raise"
            to_put = (self.current_bet - p.current_bet) + amount
            if to_put >= p.chips:
                # all-in raise
                to_put = p.chips
                p.all_in = True
            p.chips -= to_put
            p.current_bet += to_put
            self.pot += to_put
            self.current_bet = p.current_bet
            # set next to act as next active player
            nxt = self.next_active_idx(self.turn_idx)
            if nxt is not None:
                self.turn_idx = nxt
            return True, f"Raised {amount}"
        return False, "Azione non riconosciuta"

    # --- AGGIUNTA: Visualizzazione dello stato del tavolo ---
def print_table(self, reveal_all=False, player_id=None):
    print("=" * 40)
    print(f"Stato: {self.stage}, Pot: {self.pot}, Dealer: {self.dealer_idx}")
    print("Community cards:")
    print("  " + " ".join([repr(c) for c in self.community]))
    print()
    print("Giocatori:")
    for idx, p in enumerate(self.players):
        # Mostra le carte solo al proprio giocatore (o tutte in showdown)
        if reveal_all or self.stage == "showdown":
            hole_cards = " ".join([repr(c) for c in p.hole])
        elif player_id is not None and p.id == player_id:
            hole_cards = " ".join([repr(c) for c in p.hole])
        else:
            hole_cards = "XX XX"
        marker = "<-" if idx == self.turn_idx else ""
        status = "All-in" if p.all_in else ("Fold" if not p.in_hand else "")
        print(f"[{idx}] {p.name} ({p.chips} chips): {hole_cards} | Bet: {p.current_bet} {marker} {status}")
    print("=" * 40)
