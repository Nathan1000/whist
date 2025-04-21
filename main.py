import streamlit as st
import pandas as pd
from streamlit_cookies_controller import CookieController
import json
import time
import zlib, base64
import openai
import requests
from datetime import datetime
import urllib.parse




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

if "game_start_time" not in st.session_state:
    st.session_state.game_start_time = None


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
    st.session_state.rerun_pending = True  # defer rerun

def prompt_abandon():
    if COOKIE_KEY in cookies and not st.session_state.get("game_over", False):
        st.session_state.confirm_new = True
    else:
        save_scores()
        if st.session_state.get("game_over") and not st.session_state.get("scores_submitted"):
            st.sidebar.warning("Game is over but scores haven't been submitted.")
            return
        start_fresh()

def cancel_abandon():
    st.session_state.confirm_new = False
    st.session_state.rerun_pending = True

col1, col2 = st.sidebar.columns(2)

col1.button("New Game?", on_click=prompt_abandon)

if st.session_state.get("game_started") and not st.session_state.get("game_over"):
    current = st.session_state.round_num

    round_label = f"Replay Round {current}" if current > 0 else "Replay Round"
    if col2.button(round_label):
        if current > 0:
            st.session_state.round_num = current - 1
            st.session_state.awaiting_results = False
            st.session_state.guesses = {}
            st.session_state.tricks_won = {}
            if "scores_by_round" in st.session_state and len(st.session_state.scores_by_round) >= current:
                for player in st.session_state.player_order:
                    st.session_state.scores[player] -= st.session_state.scores_by_round[current - 1][player]["score"]
                st.session_state.scores_by_round = st.session_state.scores_by_round[:current - 1]
            st.session_state.save_cookie = True
            st.rerun()

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
            if key == "game_start_time":
                if st.session_state.get(key) is None:
                    st.session_state[key] = val
            elif key not in st.session_state:
                st.session_state[key] = val
    except Exception as e:
        st.error("Error restoring game state.")
        st.write(e)




def save_state_to_cookie():
    state = {
        "game_started": st.session_state.get("game_started"),
        "game_start_time": st.session_state.get("game_start_time"),
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


if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""

with st.sidebar.expander("🔑 AI Summary (Optional)"):
    st.text_input("Enter your OpenAI API key", type="password", key="openai_key")
with st.sidebar.expander("🎙️ AI Voice (Optional)"):
    st.text_input("Enter your ElevenLabs API key", type="password", key="elevenlabs_key")

if st.session_state.get("game_start_time"):
    safe_id = urllib.parse.quote(str(st.session_state["game_start_time"]))
    viewer_url = f"https://whist-score-viewer.streamlit.app/?game_id={safe_id}"
    st.sidebar.markdown(f"[📊 View Live Scores]({viewer_url})")

tab = st.sidebar.radio("Menu", ["Game", "Scores"], key="tab")
if tab == "Game":
    if "game_started" not in st.session_state:
        st.session_state.game_started = False
        st.session_state.player_order = PLAYERS.copy()

    st.title("Whist Scorekeeper :material/playing_cards:")

    if not st.session_state.game_started:
        st.subheader("Start a New Game")
        available_players = PLAYERS.copy()
        selected_order = []


        def start_game():
            st.session_state.game_started = True

            st.session_state.round_num = 0
            st.session_state.scores = {p: 0 for p in PLAYERS}
            st.session_state.scores_by_round = []
            st.session_state.game_over = False
            st.session_state.game_start_time = datetime.utcnow().isoformat()
            st.session_state.share_url = (
                "https://whist-score-viewer.streamlit.app"
                f"?game_id={urllib.parse.quote(st.session_state.game_start_time)}")

            st.session_state.save_cookie = True

        st.markdown("**Enter players in the order of play. Player 1 is first dealer:**")



        player_order = []

        player1 = st.selectbox(
            "Player 1",
            options=[p for p in PLAYERS],
            key="player_select_1"
        )
        player_order.append(player1)

        player2 = st.selectbox(
            "Player 2",
            options=[p for p in PLAYERS if p not in player_order],
            key="player_select_2"
        )
        player_order.append(player2)

        player3 = st.selectbox(
            "Player 3",
            options=[p for p in PLAYERS if p not in player_order],
            key="player_select_3"
        )
        player_order.append(player3)

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

        #Don't skip to game over if we're awaiting results
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
        col1, col2 = st.columns(2)

        if round_num == 9:
            st.subheader(f"Round {round_num + 1} | {cards_this_round} Cards | {suit_this_round}")
            with col1:
                st.info("Ian's Favourite Round!", icon=":material/info:")
        elif round_num == 4:
            st.subheader(f"Round {round_num + 1} | {cards_this_round} Cards | {suit_this_round}")
            with col1:
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

            col1, col2 = st.columns(2)
            with col1:
                if suit_this_round.startswith("Diamonds") and dealer == "Dave":
                    dealer_display = "It's...Diamond Dave!"
                else:
                    dealer_display = dealer

                st.badge(f"Dealer: {dealer_display}", icon=":material/hand_gesture:", color="green")
            with col2:
                st.badge(f"{rotated_order[0]} to lead", icon=":material/counter_1:", color="blue")

            #st.markdown("**Playing Order:** " + " → ".join(rotated_order))

            guesses = {}
            total_so_far = 0
            num_players = len(player_order)
            col1, _ = st.columns([3, 1])  # wider col1
            with col1:
                for i, player in enumerate(rotated_order):
                    if i == num_players - 1:
                        invalid_guess = cards_this_round - total_so_far
                        label = f"{player} (Can't guess {invalid_guess})" if invalid_guess >= 0 else f"{player}'s guess"
                        guess = st.number_input(
                            label,
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
            col1, col2 = st.columns([3, 1])
            for player in st.session_state.player_order:
                with col1:

                    st.session_state.tricks_won[player] = st.number_input(
                        f"{player}'s tricks won",
                        min_value=0,
                        max_value=ROUNDS[st.session_state.round_num],
                        key=f"tricks_{player}"
                )
                with col2:
                    guess = st.session_state.guesses.get(player, "—")
                    guess = st.session_state.guesses.get(player, 0)
                    tricks = st.session_state.tricks_won.get(player, 0)
                    delta = "✓" if guess == tricks else "✗"
                    emoji = "✅" if guess == tricks else "❌"
                    st.metric(label=f"{player}'s Guess:", value=f"{guess} {emoji}")

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
                try:
                    game_id = st.session_state["game_start_time"]
                    requests.post(
                        f"https://gameviewer.nathanamery.workers.dev?game_id={game_id}",
                        headers={"Content-Type": "application/json"},
                        json=st.session_state["scores_by_round"]
                    )
                except Exception as e:
                    st.warning(f"Failed to update viewer: {e}")
                # Save BEFORE incrementing
                st.session_state.save_cookie = True
                save_state_to_cookie()

                st.session_state.round_num += 1
                st.session_state.awaiting_results = False

                if st.session_state.round_num >= len(ROUNDS):
                    st.session_state.game_over = True

                st.rerun()



if tab == "Scores":
    scores_by_round = st.session_state.get("scores_by_round", [])
    if not scores_by_round:
        st.info("No hands played in this game yet")
    else:
        # Build MultiIndex columns
        rounds = [f"{ROUNDS[i]} {SUITS[i % len(SUITS)]}" for i in range(len(scores_by_round))]
        df = pd.DataFrame(index=rounds)
        for p in PLAYERS:
            df[(p, "Guess")] = [r[p]["guess"] for r in scores_by_round]
            df[(p, "Score")] = [r[p]["score"] for r in scores_by_round]
        df.columns = pd.MultiIndex.from_product([PLAYERS, ["Guess", "Score"]])

        # Add total row
        totals = {
            (p, "Guess"): "" for p in PLAYERS
        }
        final_scores = {}
        for p in PLAYERS:
            player_total = df[(p, "Score")].sum()
            totals[(p, "Score")] = player_total
            final_scores[p] = player_total
        df.loc["Total"] = totals

        # Show table
        st.dataframe(df, height=560)

        # Final rankings
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

            if st.session_state.openai_key:
                st.subheader("📣 Match Summary")

                if "summaries" not in st.session_state:
                    st.session_state.summaries = {}

                if "match_commentary" not in st.session_state:
                    st.session_state.match_commentary = ""

                style = st.selectbox("Choose commentary style", ["Football", "Formula 1"], index=0)

                if style in st.session_state.summaries:
                    commentary = st.session_state.summaries[style]
                else:
                    if style == "Football":
                        system_prompt = "You're a lively British Premier League football commentator with a flair for drama and humour. Think John Motson meets Match of the Day."
                    else:
                        system_prompt = "You're a fast-paced, excitable British Formula 1 commentator. Think David Croft with a touch of Martin Brundle, recapping key moments lap by lap."

                    prompt = f"""Use dramatic, humorous, and sports-style language to summarise a competitive countdown whist game.
        Highlight standout performances, tight rounds, unexpected plays, and pivotal moments. Be sure to slag off Russell at any opportunity.

        Here is the full match data:
        {json.dumps(st.session_state.get("scores_by_round", []), indent=2)}"""

                    try:
                        openai.api_key = st.session_state.openai_key
                        with st.spinner("Generating post-match summary..."):
                            response = openai.chat.completions.create(
                                model="gpt-4-turbo",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.9,
                            )
                            commentary = response.choices[0].message.content
                            st.session_state.summaries[style] = commentary
                            st.session_state.match_commentary = commentary
                    except Exception as e:
                        st.error("Error generating summary. Check your API key or try again later.")
                        st.exception(e)

                if st.session_state.match_commentary:
                    st.markdown(st.session_state.match_commentary)

            if st.session_state.get("match_commentary") and st.session_state.get("elevenlabs_key"):
                if st.button("🔊 Speak Summary"):
                    headers = {
                        "xi-api-key": st.session_state.elevenlabs_key,
                        "Accept": "audio/mpeg",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "text": st.session_state.match_commentary,
                        "model_id": "eleven_multilingual_v2",

                        "voice_settings": {
                            "stability": 0.73,
                            "similarity_boost": 0.75,
                            "style": 0.06,
                            "use_speaker_boost": True,
                            "speed": 1.07
                        }
                    }

                    with st.spinner("Generating audio..."):
                        response = requests.post(
                            "https://api.elevenlabs.io/v1/text-to-speech/eFsK7V4odsRpqOxGAOc8/stream",
                            headers=headers,
                            json=payload
                        )

                    if response.ok:
                        audio_data = response.content
                        st.audio(audio_data, format="audio/mpeg")
                    else:
                        st.error("Failed to get audio from ElevenLabs.")

    if st.session_state.get("game_over"):
        st.subheader("📤 Submit Scores to Sheet")

        with st.expander("Google Sheet Submission"):
            sheet_id = "1WKkTCiYHrtpOGvTccxDgtlMatEUMY_uaTGOasxxEQy0"
            password = st.text_input("Enter submission password", type="password", key="sheet_password")

            if st.button("Submit Final Scores to Sheet"):
                if not password:
                    st.warning("Password required to submit.")
                else:
                    game_start = st.session_state.get("game_start_time", "")
                    payload = {
                        "password": password,
                        "sheet_id": sheet_id,
                        "scores": [
                            {
                                "Player": player,
                                "Score": int(score),
                                "Game Start Time": game_start
                            }
                            for player, score in final_scores.items()
                        ]
                    }
                    try:
                        with st.spinner("Submitting scores..."):
                            res = requests.post(
                                "https://whist-saver.nathanamery.workers.dev",
                                headers={"Content-Type": "application/json"},
                                json=payload
                            )
                        if res.status_code == 200:
                            st.success("✅ Scores submitted successfully!")
                            st.session_state.scores_submitted = True
                            st.markdown(f"[View Sheet](https://docs.google.com/spreadsheets/d/{sheet_id})")
                        elif res.status_code == 207:
                            st.warning(res.text)
                            st.markdown(f"[View Sheet](https://docs.google.com/spreadsheets/d/{sheet_id})")
                        else:
                            st.error(f"❌ Error: {res.text}")
                    except Exception as e:
                        st.error("Failed to submit scores.")
                        st.exception(e)

if st.session_state.get("game_start_time"):
    st.markdown(
        f"<footer style='text-align: center; font-size: 0.75rem; color: gray;'>"
        f"Game ID: {st.session_state['game_start_time']}</footer>",
        unsafe_allow_html=True
    )