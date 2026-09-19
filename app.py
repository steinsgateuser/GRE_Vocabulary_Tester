import random
from datetime import datetime

from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    session,
    redirect,
    url_for
)

from database import (
    init_db,
    get_user_by_username,
    get_user_progress,
    record_answer,
    get_dashboard_stats,
    get_review_words
)

from vocab_processing import get_vocab_data, normalize_word


app = Flask(__name__)

app.secret_key = "gre-vocabulary-development-key"

init_db()

df = get_vocab_data()

print(f"Total vocabulary: {len(df)} rows")


# ============================================================
# LEARNING QUEUE
# ============================================================

def generate_learning_test(user_id, batch_size=20):

    progress_data = get_user_progress(user_id)

    progress_map = {
        item["word"]: item
        for item in progress_data
    }

    current_batch = session.get("batch_number", 1)

    review_words = []
    validation_words = []
    new_words = []

    for _, row in df.iterrows():

        word = row["Word"]

        item = progress_map.get(word)

        if item is None:

            new_words.append(word)
            continue

        status = item["status"]
        progress = item["progress"]
        last_batch = item.get("last_batch", 0)

        if status == "MASTERED":
            continue

        # REVIEW words are always eligible.
        if status == "REVIEW":

            review_words.append(
                (last_batch, word)
            )
            continue

        # Validation words need one full batch gap.
        if (
            status == "NEW"
            and progress == 1
            and current_batch > last_batch
        ):

            validation_words.append(
                (last_batch, word)
            )
            continue

        # Otherwise ignore for this batch.

    review_words.sort(key=lambda x: x[0])
    validation_words.sort(key=lambda x: x[0])

    review_words = [word for _, word in review_words]
    validation_words = [word for _, word in validation_words]

    random.shuffle(new_words)

    review_quota = round(batch_size * 0.30)
    validation_quota = round(batch_size * 0.40)
    new_quota = batch_size - review_quota - validation_quota

    selected = []

    selected.extend(review_words[:review_quota])
    selected.extend(validation_words[:validation_quota])
    selected.extend(new_words[:new_quota])

    if len(selected) < batch_size:

        selected_set = set(selected)

        remaining = (
            [w for w in review_words if w not in selected_set]
            + [w for w in validation_words if w not in selected_set]
            + [w for w in new_words if w not in selected_set]
        )

        selected.extend(
            remaining[:batch_size - len(selected)]
        )

    selected_df = df[
        df["Word"].isin(selected[:batch_size])
    ].copy()

    return selected_df


# ============================================================
# QUESTION GENERATION
# ============================================================

def build_questions(test_df):
    """Convert vocabulary rows into multiple-choice questions."""

    test_questions = []

    for _, row in test_df.iterrows():

        word = row["Word"]

        target_cluster = row["Cluster"]

        correct_connotation = row["Connotation"]

        # ----------------------------------------------------
        # Get incorrect meanings from other clusters
        # ----------------------------------------------------

        other_df = df[
            (df["Cluster"] != target_cluster)
            & (df["Connotation"].notna())
        ]

        other_connotations = (
            other_df["Connotation"]
            .astype(str)
            .str.strip()
            .drop_duplicates()
            .tolist()
        )

        other_connotations = [
            connotation
            for connotation in other_connotations
            if connotation != correct_connotation
        ]

        if len(other_connotations) < 2:

            raise ValueError(
                "Not enough unique connotations "
                "from other clusters."
            )

        wrong_connotations = random.sample(
            other_connotations,
            2
        )

        # ----------------------------------------------------
        # Create options
        # ----------------------------------------------------

        options = [
            {
                "text": correct_connotation,
                "correct": True
            },
            {
                "text": wrong_connotations[0],
                "correct": False
            },
            {
                "text": wrong_connotations[1],
                "correct": False
            }
        ]

        random.shuffle(options)

        test_questions.append({
            "word": word,
            "options": options
        })

    # Randomize question order

    random.shuffle(test_questions)

    return test_questions


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "user_id" not in session:

        return render_template(
            "login.html"
        )

    return render_template(
        "index.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:

        return jsonify({
            "error": "No user selected."
        }), 400

    username = data.get("username")

    if username not in ["Polo", "Tusu"]:

        return jsonify({
            "error": "Invalid user."
        }), 400

    user = get_user_by_username(
        username
    )

    if not user:

        return jsonify({
            "error": "User not found."
        }), 404

    session["user_id"] = user["id"]

    session["username"] = user["username"]

    return jsonify({
        "success": True,
        "username": user["username"]
    })


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/api/dashboard")
def dashboard():

    if "user_id" not in session:

        return jsonify({
            "error": "Not logged in."
        }), 401

    stats = get_dashboard_stats(
        session["user_id"],
        len(df)
    )

    return jsonify(stats)


# ============================================================
# RECORD ANSWER
# ============================================================

@app.route(
    "/api/record-answer",
    methods=["POST"]
)
def record_user_answer():

    if "user_id" not in session:

        return jsonify({
            "error": "Not logged in."
        }), 401

    data = request.get_json()

    if not data:

        return jsonify({
            "error": "No request data received."
        }), 400

    word = data.get("word")

    correct = data.get("correct")

    if not word:

        return jsonify({
            "error": "Word is required."
        }), 400

    if not isinstance(correct, bool):

        return jsonify({
            "error": "Correct must be true or false."
        }), 400

    try:

        record_answer(
            session["user_id"],
            word,
            correct,
            session.get("batch_number", 1)
        )

        return jsonify({
            "success": True
        })

    except Exception as e:

        print(
            "ERROR RECORDING ANSWER:",
            e
        )

        return jsonify({
            "error": "Failed to record answer."
        }), 500


# ============================================================
# REVIEW WORDS
# ============================================================

@app.route("/api/review-words")
def review_words():

    if "user_id" not in session:

        return jsonify({
            "error": "Not logged in."
        }), 401

    words = get_review_words(
        session["user_id"]
    )

    result = []

    for item in words:

        match = df[
            df["Word_Normalized"]
            == normalize_word(item["word"])
        ]

        meaning = ""

        if not match.empty:
            meaning = match.iloc[0]["Connotation"]

        result.append({
            "word": item["word"],
            "meaning": meaning,
            "progress": item["progress"],
            "correct_count": item["correct_count"],
            "wrong_count": item["wrong_count"]
        })

    return jsonify({
        "words": result
    })

# ============================================================
# START LEARNING TEST
# ============================================================

@app.route("/api/start-test", methods=["POST"])
def start_test():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    try:
        print("SESSION BEFORE TEST:", dict(session))

        if "batch_number" not in session:
            session["batch_number"] = 1

        test_df = generate_learning_test(
            session["user_id"],
            batch_size=100
        )

        if test_df.empty:
            return jsonify({
                "questions": [],
                "message": "All vocabulary words have been mastered."
            })

        questions = build_questions(test_df)

        session["batch_number"] += 1

        return jsonify({"questions": questions})

    except Exception as e:
        import traceback
        print("ERROR STARTING TEST:", repr(e))
        traceback.print_exc()
        return jsonify({"error": "Failed to generate test."}), 500

# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )