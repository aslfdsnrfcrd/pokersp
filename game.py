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
    """Accetta anche '10' e lo mappa a 'T' internamente."""
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
        # Rappresenta 10 come "10" per leggibilità, ma mantiene internamente 'T'
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

# --- Funzioni di Valutazione ---

def is_straight(values):
    vals = sorted(set(values), reverse=True)
    # A-5 low straight (Aces are 1 or 14)
    if 14 in vals:
        vals.append(1)
    for i in range(len(vals) - 4):
        window = vals[i:i + 5]
        if len(window) == 5 and all(window[j] - window[j + 1] == 1 for j in range(4)):
            return window[0]  # Ritorna la carta alta della scala
    return None

def evaluate_5cards(cards: List[Card]):
    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    # Ordina per conteggio discendente, poi per valore discendente
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
