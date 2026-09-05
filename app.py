import random

from flask import Flask, render_template, jsonify, request

from vocab_processing import get_vocab_data

# ---------------------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Load vocabulary
# ---------------------------------------------------------------------------

df, level_1_df, level_2_df = get_vocab_data()

print(f"Total vocabulary: {len(level_2_df)} rows")
print(f"Level 1 vocabulary: {len(level_1_df)} rows")


# ---------------------------------------------------------------------------
# Test generation
# ---------------------------------------------------------------------------

def generate_test(number_of_words, level):
    """Build a list of multiple-choice vocabulary questions."""

    # Select vocabulary pool for the requested level
    test_pool = level_1_df.copy() if level == 1 else level_2_df.copy()

    # Remove rows missing required fields
    test_pool = test_pool.dropna(subset=["Word", "Connotation", "Cluster"])

    if len(test_pool) == 0:
        raise ValueError(f"No vocabulary words available for Level {level}.")

    # Don't ask for more words than exist
    number_of_words = min(number_of_words, len(test_pool))

    # Randomly select distinct words
    test_df = test_pool.sample(n=number_of_words, replace=False).reset_index(drop=True)

    test_questions = []

    for _, row in test_df.iterrows():
        word = row["Word"]
        target_cluster = row["Cluster"]
        correct_connotation = row["Connotation"]

        # Candidate wrong answers: different cluster, non-null connotation
        other_df = df[(df["Cluster"] != target_cluster) & (df["Connotation"].notna())]

        other_connotations = (
            other_df["Connotation"]
            .astype(str)
            .str.strip()
            .drop_duplicates()
            .tolist()
        )

        # Exclude the correct answer from the distractor pool
        other_connotations = [
            connotation
            for connotation in other_connotations
            if connotation != correct_connotation
        ]

        if len(other_connotations) < 2:
            raise ValueError("Not enough unique connotations from other clusters.")

        wrong_connotations = random.sample(other_connotations, 2)

        options = [
            {"text": correct_connotation, "correct": True},
            {"text": wrong_connotations[0], "correct": False},
            {"text": wrong_connotations[1], "correct": False},
        ]
        random.shuffle(options)

        test_questions.append({"word": word, "options": options})

    return test_questions


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/start-test", methods=["POST"])
def start_test():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No request data received."}), 400

    level = data.get("level")
    number_of_words = data.get("number_of_words")

    # Validate level
    try:
        level = int(level)
    except (TypeError, ValueError):
        return jsonify({"error": "Please select a valid level."}), 400

    if level not in (1, 2):
        return jsonify({"error": "Level must be either 1 or 2."}), 400

    # Validate number of words
    try:
        number_of_words = int(number_of_words)
    except (TypeError, ValueError):
        return jsonify({"error": "Number of words must be an integer."}), 400

    if number_of_words < 1:
        return jsonify({"error": "Number of words must be at least 1."}), 400

    # Check vocabulary availability for the selected level
    available_words = len(level_1_df) if level == 1 else len(level_2_df)

    if available_words == 0:
        return jsonify({"error": f"No vocabulary words are available for Level {level}."}), 400

    if number_of_words > available_words:
        return jsonify({"error": f"Only {available_words} words are available for Level {level}."}), 400

    # Generate the test
    try:
        questions = generate_test(number_of_words, level)
    except Exception as e:
        print("ERROR GENERATING TEST:", e)
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "level": level,
        "total_questions": len(questions),
        "questions": questions,
    })


# ---------------------------------------------------------------------------
# Run app
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)