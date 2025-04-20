import streamlit as st
import pandas as pd
from streamlit_cookies_controller import CookieController
import json
import time
import zlib, base64


PLAYERS = ["Campbell", "Russell", "Nathan", "Dave"]
SUITS = ["Hearts ♥️", "Clubs ♣️", "Diamonds ♦️", "Spades ♠️", "No Trumps 🙅🏻"]
ROUNDS = list(range(7, 0, -1)) + list(range(2, 8))  # 7 to 1, then 2 to 7

# Init cookie controller
controller = CookieController()
cookies = controller.getAll()

# Abort if not ready
if not cookies:
    st.stop()

def save_scores():
    # TODO: implement saving to external DB
    scores = st.session_state.get("scores_by_round", [])
    # placeholder for later DB logic
    print("Save Scores placeholder:", scores)

COOKIE_KEY = "whist_state"

if "confirm_new" not in st.session_state:
    st.session_state.confirm_new = False

if "confirm_new" not in st.session_state:
    st.session_state.confirm_new = False

def start_fresh():
    # only try removal if it actually exists
    try:
        current = controller.getAll()
        if COOKIE_KEY in current:
            controller.remove(COOKIE_KEY)
    except Exception as e:
        st.sidebar.error(f"Error removing cookie: {e}")
    # clear all session_state
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state.tab = "Game"
    st.rerun()

def prompt_abandon():
    if COOKIE_KEY in cookies and not st.session_state.get("game_over", False):
        st.session_state.confirm_new = True
    else:
        save_scores()
        start_fresh()

def cancel_abandon():
    st.session_state.confirm_new = False
    st.session_state.rerun_pending = True

# Primary “New Game?” button
st.sidebar.button("New Game?", on_click=prompt_abandon)

# Confirmation UI
if st.session_state.confirm_new:
    st.sidebar.warning("Are you sure you want to abandon the current game?")
    st.sidebar.button("Yes, abandon",  on_click=start_fresh)
    st.sidebar.button("No, continue", on_click=cancel_abandon)




# Restore from cookie
if COOKIE_KEY in cookies:
    try:
        raw = cookies[COOKIE_KEY]
        if isinstance(raw, str):
            try:
                decoded = base64.b64decode(raw)
                txt = zlib.decompress(decoded).decode('utf-8')
            except Exception:
                txt = raw
        saved = json.loads(txt)
        for key, val in saved.items():
            if key not in st.session_state:
                st.session_state[key] = val
    except Exception as e:
        st.error("Error restoring game state.")
        st.write(e)




def save_state_to_cookie():
    state = {
        "game_started": st.session_state.get("game_started"),
        "round_num": st.session_state.get("round_num"),
        "player_order": st.session_state.get("player_order"),
        "scores": st.session_state.get("scores"),
        "scores_by_round": st.session_state.get("scores_by_round"),
        "guesses": st.session_state.get("guesses"),
        "awaiting_results": st.session_state.get("awaiting_results"),
        "game_over": st.session_state.get("game_over"),
    }
    time.sleep(0.5)
    raw = json.dumps(state).encode('utf-8')
    compressed = base64.b64encode(zlib.compress(raw)).decode('ascii')
    controller.set(COOKIE_KEY, compressed, max_age=30 * 24 * 60 * 60)

# Save on rerun cycle
if st.session_state.get("save_cookie"):
    save_state_to_cookie()
    st.session_state.save_cookie = False

if st.session_state.get("rerun_pending"):
    st.session_state.rerun_pending = False
    st.rerun()


tab = st.sidebar.radio("Menu", ["Game", "Scores"], key="tab")
if tab == "Game":
    if "game_started" not in st.session_state:
        st.session_state.game_started = False
        st.session_state.player_order = PLAYERS.copy()

    st.title("Whist Scorekeeper :material/playing_cards:")

    if not st.session_state.game_started:
        st.subheader("Start a New Game")
        col1, col2 = st.columns(2)
        available_players = PLAYERS.copy()
        selected_order = []


        def start_game():
            st.session_state.game_started = True
            st.session_state.round_num = 0
            st.session_state.scores = {p: 0 for p in PLAYERS}
            st.session_state.scores_by_round = []
            st.session_state.game_over = False


        st.markdown("**Enter players in the order of play (exactly 4):**")

        col1, col2 = st.columns(2)

        player_order = []

        with col1:
            player1 = st.selectbox(
                "Player 1",
                options=[p for p in PLAYERS],
                key="player_select_1"
            )
            player_order.append(player1)

        with col2:
            player2 = st.selectbox(
                "Player 2",
                options=[p for p in PLAYERS if p not in player_order],
                key="player_select_2"
            )
            player_order.append(player2)

        with col1:
            player3 = st.selectbox(
                "Player 3",
                options=[p for p in PLAYERS if p not in player_order],
                key="player_select_3"
            )
            player_order.append(player3)

        with col2:
            player4 = st.selectbox(
                "Player 4",
                options=[p for p in PLAYERS if p not in player_order],
                key="player_select_4"
            )
            player_order.append(player4)

        st.session_state.player_order = player_order

        if len(set(player_order)) == 4:
            st.button("Start Game", on_click=start_game)
    else:
        round_num = st.session_state.round_num

        # ⛔ Don't skip to game over if we're awaiting results
        if not st.session_state.get("awaiting_results") and (
                st.session_state.get("game_over") or round_num >= len(ROUNDS)
        ):
            st.subheader("🎉 Game Over!")
            st.markdown("The game has ended. Check the **Scores** tab to see final results.")
            st.session_state.save_cookie = True
            st.stop()
        if round_num >= len(ROUNDS):
            st.session_state.game_over = True
            st.session_state.save_cookie = True
            save_state_to_cookie()
            st.stop()
        cards_this_round = ROUNDS[round_num]
        suit_this_round = SUITS[round_num % len(SUITS)]

        if round_num == 9:
            st.subheader(f"Round {round_num + 1} | {cards_this_round} Cards | {suit_this_round}")
            st.info("Ian's Favourite Round!", icon=":material/info:")
        elif round_num == 4:
            st.subheader(f"Round {round_num + 1} | {cards_this_round} Cards | {suit_this_round}")
            st.info("Ian's second Favourite Round!", icon=":material/info:")

        else:
            st.subheader(f"Round {round_num + 1} | {cards_this_round} Cards | {suit_this_round}")

        if not st.session_state.get("awaiting_results"):
            st.write("Enter Guesses")

            player_order = st.session_state.player_order
            dealer_index = round_num % len(player_order)
            dealer = player_order[dealer_index]

            # Rotate order so next after dealer starts
            rotated_order = player_order[dealer_index + 1:] + player_order[:dealer_index + 1]

            st.badge(f"Dealer: {dealer} ", icon=":material/hand_gesture:", color="green")
            st.badge(f"{rotated_order[0]} to lead", icon=":material/counter_1:",  color="blue")

            #st.markdown("**Playing Order:** " + " → ".join(rotated_order))

            guesses = {}
            total_so_far = 0
            num_players = len(player_order)

            for i, player in enumerate(rotated_order):
                if i == num_players - 1:
                    invalid_guess = cards_this_round - total_so_far
                    if invalid_guess >= 0:
                        st.info(f"{player} can't guess {invalid_guess}", icon=":material/info:")
                    guess = st.number_input(
                        f"{player}'s guess",
                        min_value=0,
                        max_value=cards_this_round,
                        key=f"guess_{player}",
                    )
                else:
                    guess = st.number_input(
                        f"{player}'s guess",
                        min_value=0,
                        max_value=cards_this_round,
                        key=f"guess_{player}",
                    )
                    total_so_far += guess
                guesses[player] = guess

            valid_guesses = (
                    len(guesses) == num_players
                    and guesses[rotated_order[-1]] != cards_this_round - total_so_far
            )

            if valid_guesses:
                if st.button("Submit Guesses"):
                    st.session_state.guesses = guesses
                    st.session_state.awaiting_results = True
                    st.session_state.save_cookie = True
                    save_state_to_cookie()
                    st.rerun()


            else:
                st.warning(f"{rotated_order[-1]}'s guess can't be {invalid_guess}")

        if st.session_state.get("awaiting_results"):
            st.write("Enter Tricks Won")

            if "tricks_won" not in st.session_state:
                st.session_state.tricks_won = {}

            for player in st.session_state.player_order:
                st.session_state.tricks_won[player] = st.number_input(
                    f"{player}'s tricks won",
                    min_value=0,
                    max_value=ROUNDS[st.session_state.round_num],
                    key=f"tricks_{player}"
                )

            total_tricks = sum(st.session_state.tricks_won.values())
            cards_this_round = ROUNDS[st.session_state.round_num]

            if total_tricks != cards_this_round:
                st.info(f"Total tricks must equal {cards_this_round}. Currently: {total_tricks}")
                submit_disabled = True
            else:
                submit_disabled = False


            if st.button("Submit Results", disabled=submit_disabled):
                # print("DEBUG: Submit Results clicked")
                # print(f"DEBUG: round_num before submit: {st.session_state.round_num}")
                # print(f"DEBUG: len(ROUNDS): {len(ROUNDS)}")

                round_data = {}
                for player in st.session_state.player_order:
                    guess = st.session_state.guesses.get(player, 0)
                    tricks = st.session_state.tricks_won.get(player, 0)
                    score = 10 + tricks if guess == tricks else tricks
                    st.session_state.scores[player] += score
                    round_data[player] = {"guess": guess, "score": score}

                if "scores_by_round" not in st.session_state:
                    st.session_state.scores_by_round = []
                st.session_state.scores_by_round.append(round_data)

                # Save BEFORE incrementing
                st.session_state.save_cookie = True
                save_state_to_cookie()

                st.session_state.round_num += 1
                st.session_state.awaiting_results = False

                if st.session_state.round_num >= len(ROUNDS):
                    st.session_state.game_over = True

                print(f"DEBUG: round_num after submit: {st.session_state.round_num}")
                st.rerun()


if tab == "Scores":
    scores_by_round = st.session_state.get("scores_by_round", [])
    if not scores_by_round:
        st.write("No scores yet.")
    else:
        # build MultiIndex columns
        rounds = [f"{ROUNDS[i]} {SUITS[i % len(SUITS)]}" for i in range(len(scores_by_round))]
        df = pd.DataFrame(index=rounds)
        for p in PLAYERS:
            df[(p, "Guess")] = [r[p]["guess"] for r in scores_by_round]
            df[(p, "Score")] = [r[p]["score"] for r in scores_by_round]
        df.columns = pd.MultiIndex.from_product([PLAYERS, ["Guess", "Score"]])
        # add total row
        totals = {}
        final_scores={}
        for p in PLAYERS:
            totals[(p, "Guess")] = ""
            totals[(p, "Score")] = df[(p, "Score")].sum()
        df.loc["Total"] = totals
        st.dataframe(df, height=560)

        if st.session_state.get("round_num", 0) >= len(ROUNDS):
            st.subheader("🏆 Final Rankings")
            sorted_scores = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
            rankings, last_score, current_rank, offset = [], None, 0, 1
            for player, score in sorted_scores:
                if score != last_score:
                    current_rank = offset
                rankings.append((current_rank, player, score))
                last_score = score
                offset += 1
            for rank, player, score in rankings:
                st.markdown(f"**{rank}. {player}** – {score} points")



