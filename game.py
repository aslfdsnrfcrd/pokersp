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
        drawn = self.cards[:]()
