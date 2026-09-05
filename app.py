import random

from flask import Flask, render_template, jsonify, request

from vocab_processing import get_vocab_data, normalize_word

app = Flask(__name__)

df = get_vocab_data()

print(f"Total vocabulary: {len(df)} rows")


def generate_test(number_of_words):
    """Generate a random test from the complete vocabulary."""

    test_pool = df.copy()

    test_pool = test_pool.dropna(
        subset=["Word", "Connotation", "Cluster"]
    )

    if len(test_pool) == 0:
        raise ValueError("No vocabulary words available.")

    number_of_words = min(number_of_words, len(test_pool))

    test_df = test_pool.sample(
        n=number_of_words,
        replace=False
    ).reset_index(drop=True)

    return build_questions(test_df)


def generate_test_from_words(words):
    """Generate a test using only the supplied vocabulary words."""

    if not words:
        raise ValueError("No mistake words were supplied.")

    requested_words = {
        normalize_word(word)
        for word in words
        if str(word).strip()
    }

    test_pool = df[
        df["Word_Normalized"].isin(requested_words)
    ].copy()

    test_pool = test_pool.dropna(
        subset=["Word", "Connotation", "Cluster"]
    )

    if len(test_pool) == 0:
        raise ValueError("None of the supplied words were found.")

    # Keep one row per requested word.
    test_pool = (
        test_pool
        .drop_duplicates(subset=["Word_Normalized"])
        .reset_index(drop=True)
    )

    return build_questions(test_pool)


def build_questions(test_df):
    """Convert vocabulary rows into multiple-choice questions."""

    test_questions = []

    for _, row in test_df.iterrows():
        word = row["Word"]
        target_cluster = row["Cluster"]
        correct_connotation = row["Connotation"]

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
                "Not enough unique connotations from other clusters."
            )

        wrong_connotations = random.sample(
            other_connotations,
            2
        )

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

    random.shuffle(test_questions)

    return test_questions


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/start-test", methods=["POST"])
def start_test():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "No request data received."
        }), 400

    mistake_words = data.get("mistake_words")

    # Revisit mistakes mode
    if mistake_words is not None:
        if not isinstance(mistake_words, list):
            return jsonify({
                "error": "Mistake words must be a list."
            }), 400

        if len(mistake_words) == 0:
            return jsonify({
                "error": "No mistake words available."
            }), 400

        try:
            questions = generate_test_from_words(
                mistake_words
            )
        except Exception as e:
            print("ERROR GENERATING REVIEW TEST:", e)

            return jsonify({
                "error": str(e)
            }), 500

        return jsonify({
            "total_questions": len(questions),
            "questions": questions,
            "mode": "mistakes"
        })

    # Normal test mode
    number_of_words = data.get("number_of_words")

    try:
        number_of_words = int(number_of_words)
    except (TypeError, ValueError):
        return jsonify({
            "error": "Number of words must be an integer."
        }), 400

    if number_of_words < 1:
        return jsonify({
            "error": "Number of words must be at least 1."
        }), 400

    available_words = len(
        df.dropna(subset=["Word", "Connotation", "Cluster"])
    )

    if available_words == 0:
        return jsonify({
            "error": "No vocabulary words are available."
        }), 400

    if number_of_words > available_words:
        return jsonify({
            "error": f"Only {available_words} words are available."
        }), 400

    try:
        questions = generate_test(number_of_words)
    except Exception as e:
        print("ERROR GENERATING TEST:", e)

        return jsonify({
            "error": str(e)
        }), 500

    return jsonify({
        "total_questions": len(questions),
        "questions": questions,
        "mode": "normal"
    })


if __name__ == "__main__":
    app.run(debug=True)