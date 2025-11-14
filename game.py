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
        self.last_raiser_idx = -1  # Traccia l'ultima persona che ha rilanciato/puntato
        self.last_raise_amount = bb  # Ultimo incremento (min raise)

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

    # --- Helper per flush delle puntate nel pot ---
    def flush_current_bets_to_pot(self):
        """
        Sposta tutte le current_bet (dei giocatori) nel pot e azzera current_bet.
        Deve essere chiamato *solo* al termine di un betting round o quando si conclude la mano.
        """
        bets = sum(p.current_bet for p in self.players)
        if bets > 0:
            self.pot += bets
            for p in self.players:
                p.current_bet = 0

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
        self.last_raiser_idx = -1
        self.last_raise_amount = self.bb

        # deal 2 cards
        for _ in range(2):
            for p in self.players:
                p.hole.append(self.deck.draw(1)[0])

        # post blinds
        self.dealer_idx = self.dealer_idx % len(self.players)  # Assicura che l'indice sia valido
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

        # Metti blind nel pot direttamente (sono puntate iniziali)
        self.pot += sb_amt + bb_amt
        self.current_bet = bb_amt

        # first to act is player after BB
        self.turn_idx = (bb_idx + 1) % len(self.players)
        self.last_raiser_idx = bb_idx  # La BB è l'ultima "puntata" obbligatoria

        return True, "Mano iniziata"

    def advance_stage(self):
        """
        Avanza la fase: prima flusha le puntate nel pot, poi distribuisce le community cards.
        Gestisce anche il caso in cui tutti siano all-in (auto-showdown).
        """
        # Porta le puntate correnti nel pot (fine betting round)
        self.flush_current_bets_to_pot()

        if self.stage == "preflop":
            # Flop
            self.community.extend(self.deck.draw(3))
            self.stage = "flop"
        elif self.stage == "flop":
            # Turn
            self.community.extend(self.deck.draw(1))
            self.stage = "turn"
        elif self.stage == "turn":
            # River
            self.community.extend(self.deck.draw(1))
            self.stage = "river"
        elif self.stage == "river":
            self.stage = "showdown"
        else:
            # Dopo lo showdown, prepara il gioco per la prossima mano
            self.started = False
            self.stage = "waiting"
            # Muove il dealer alla mano successiva
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players) if self.players else 0
            return

        # reset current bets for next round (already done by flush_current_bets_to_pot)
        self.current_bet = 0
        self.last_raiser_idx = -1
        self.last_raise_amount = self.bb

        # next to act is player after dealer (first non-folded/non-all-in player)
        start = self.dealer_idx
        nxt = self.next_active_idx(start)
        if nxt is None:
            # Se non c'è nessuno che deve agire (es. tutti all-in), avanzare automaticamente fino a showdown
            while self.stage != "showdown":
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
            return
        else:
            self.turn_idx = nxt

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
        """
        Cerca il prossimo giocatore che deve agire.
        Restituisce None se nessuno deve agire (giro finito).
        Questa versione evita il loop infinito quando tutti fanno check.
        """
        n = len(self.players)
        # Cerca giocatore che deve ancora eguagliare la puntata
        for i in range(1, n + 1):
            idx = (start + i) % n
            p = self.players[idx]
            if p.in_hand and not p.all_in and p.current_bet < self.current_bet:
                return idx

        # Se current_bet == 0 (tutti possono check), non restituire un giocatore:
        # significa che il giro può considerarsi finito (tutti hanno la stessa puntata)
        if self.current_bet == 0:
            return None

        # Nessuno deve agire
        return None

    def is_betting_round_over(self):
        # Un giro di puntate è finito se:
        # 1. Tutti i giocatori in mano (anche all-in) sono pari alla puntata massima
        # 2. Ci sono almeno due giocatori in mano
        if self.all_but_one_folded():
            return True

        for p in self.players:
            if p.in_hand and not p.all_in and p.current_bet < self.current_bet:
                return False

        # Se si è qui, tutti sono o pari o all-in. Il giro è finito.
        return True

    def all_but_one_folded(self):
        inplay = [p for p in self.players if p.in_hand]
        return len(inplay) <= 1

    # Nota: Questa funzione assegna solo il piatto principale (senza side pots).
    # Assicura che il pot contenga tutte le puntate rilevanti (flush current bets prima).
    def collect_pots_and_award(self):
        """
        Assegna il pot principale ai vincitori. Non gestisce side-pots complessi.
        Assumiamo che tutte le puntate siano già state flushate nel pot quando necessario.
        """
        inplay = [p for p in self.players if p.in_hand]
        results = []

        # 1. Un solo giocatore rimasto
        if len(inplay) == 1:
            winner = inplay[0]
            winner.chips += self.pot
            results.append({"winner_name": winner.name, "amount": self.pot, "hand": "Unico Rimasto"})
            self.pot = 0
            # fine mano
            self.started = False
            self.stage = "waiting"
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players) if self.players else 0
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
        if len(winners) == 0:
            # Nessun vincitore (improbabile) -> rimetti le puntate a tutti (fallback)
            self.pot = 0
            return []

        split = self.pot // len(winners)
        remaining = self.pot % len(winners)  # Gestione arrotondamento

        for i, (w, hand_type) in enumerate(winners):
            amount = split
            if i == 0:
                amount += remaining
            w.chips += amount
            results.append({"winner_name": w.name, "amount": amount, "hand": hand_type})

        self.pot = 0
        # fine mano
        self.started = False
        self.stage = "waiting"
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players) if self.players else 0
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
            # Se rimane un solo giocatore, raccogli il piatto e termina la mano
            if self.all_but_one_folded():
                # Porta le puntate correnti nel pot, assegna e termina
                self.flush_current_bets_to_pot()
                results = self.collect_pots_and_award()
                return True, f"Hai foldato. Mano terminata. Risultati: {results}"

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

            # Avanza il turno: cerca prossimo che deve agire; se nessuno, chiudi il giro
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

            if p.chips == 0:
                p.all_in = True

            # Avanza il turno
            nxt = self.next_active_idx(self.turn_idx)
            if nxt is None:
                self.advance_stage()
            else:
                self.turn_idx = nxt
            return True, f"Call {put}"

        # --- Raise / Bet ---
        if action == "raise":
            if amount <= 0:
                return False, "Specifica un importo di rilancio valido."

            to_call = self.current_bet - p.current_bet
            # amount è l'incremento desiderato (non il totale)
            min_inc = self.last_raise_amount if self.last_raiser_idx != -1 else self.bb
            if amount < min_inc and (to_call + amount) < p.chips:
                return False, f"L'incremento del rilancio deve essere di almeno {min_inc}."

            to_put = to_call + amount

            # All-in
            if to_put >= p.chips:
                to_put = p.chips
                p.all_in = True

            p.chips -= to_put
            p.current_bet += to_put

            # Aggiorna la puntata corrente del tavolo solo se è maggiore
            if p.current_bet > self.current_bet:
                actual_inc = p.current_bet - self.current_bet
                self.current_bet = p.current_bet
                self.last_raiser_idx = self.turn_idx
                self.last_raise_amount = actual_inc

            # Avanza il turno
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
    game = Game(max_players=6, sb=10, bb=20)

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

    for name in player_names:
        game.add_player(name)

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
        while game.started and game.stage != "showdown" and not game.all_but_one_folded():
            print(f"\n--- Fase: {game.stage.upper()} ---")

            # Trova l'ID del giocatore di turno per mostrare solo le sue carte
            if not game.started: break
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
                    action_prompt = f"Azione (call {to_call} / raise <incremento> / fold): "

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

            # Dopo l'azione, se il betting round è terminato, avanza la fase
            if game.is_betting_round_over() and game.started:
                game.advance_stage()

        # Assegnazione del piatto
        if not game.started or game.stage == "showdown":
            if game.started and game.stage == "showdown":
                # Assicuriamoci di mettere eventuali puntate residue nel pot
                game.flush_current_bets_to_pot()
                print("\n--- SHOWDOWN ---")
            else:
                # Se la mano è finita per fold, le puntate sono state flushate/gestite già
                print("\n--- Mano Terminata per Fold ---")

            game.print_table(reveal_all=True)
            winners = game.collect_pots_and_award()
            print("\n🏆 VINCITORI E ASSEGNAZIONE PIATTO:")
            for result in winners:
                print(f"- **{result['winner_name']}** vince **{result['amount']}** fiches con un **{result['hand']}**.")

            hand_num += 1

    print("\n\n--- PARTITA TERMINATA ---")
    final_players = sorted([p for p in game.players if p.chips > 0], key=lambda p: p.chips, reverse=True)
    for p in final_players:
        print(f"Classifica: {p.name} con {p.chips} fiches.")


if __name__ == "__main__":
    main()
__all__ = ["Game"]
