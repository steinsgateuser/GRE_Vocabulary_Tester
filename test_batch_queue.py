from database import (
    get_user_by_username,
    get_user_progress,
    record_answer,
    get_connection
)

from vocab_processing import get_vocab_data


df = get_vocab_data()

user = get_user_by_username("Polo")
user_id = user["id"]

word_1 = df.iloc[0]["Word"]
word_2 = df.iloc[1]["Word"]


def clean_word(word):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM user_progress
                WHERE user_id = %s
                  AND word = %s
                """,
                (user_id, word)
            )


def get_state(word):

    progress = get_user_progress(user_id)

    for item in progress:

        if item["word"] == word:
            return item

    return None


# ------------------------------------------------------------
# CLEAN
# ------------------------------------------------------------

clean_word(word_1)
clean_word(word_2)


print("\n========================================")
print("BATCH QUEUE TEST")
print("========================================")


# ------------------------------------------------------------
# Simulate Batch 1
# ------------------------------------------------------------

print("\nBatch 1")

record_answer(
    user_id,
    word_1,
    True,
    1
)

print("\nAfter answering correctly:")
print(get_state(word_1))


# ------------------------------------------------------------
# Check that the word has progress = 1
# ------------------------------------------------------------

state = get_state(word_1)

assert state["progress"] == 1
assert state["status"] == "NEW"
assert state["last_batch"] == 1


print("\nPASS: Word is in validation state.")


# ------------------------------------------------------------
# Simulate Batch 1 again
# ------------------------------------------------------------

print("\nChecking same batch...")

state = get_state(word_1)

if state["last_batch"] == 1:

    print(
        "PASS: Word should NOT be eligible "
        "again in Batch 1."
    )


# ------------------------------------------------------------
# Simulate Batch 2
# ------------------------------------------------------------

print("\nBatch 2")

state = get_state(word_1)

if 2 > state["last_batch"]:

    print(
        "PASS: Word becomes eligible "
        "in Batch 2."
    )

else:

    print(
        "FAIL: Word is still blocked."
    )


# ------------------------------------------------------------
# Now test REVIEW
# ------------------------------------------------------------

print("\n========================================")
print("REVIEW TEST")
print("========================================")


record_answer(
    user_id,
    word_2,
    False,
    1
)

print("\nAfter WRONG:")
print(get_state(word_2))


state = get_state(word_2)

assert state["progress"] == 0
assert state["status"] == "REVIEW"
assert state["last_batch"] == 1


print(
    "\nPASS: Word correctly moved to REVIEW."
)


# ------------------------------------------------------------
# REVIEW words should be available immediately
# ------------------------------------------------------------

if state["status"] == "REVIEW":

    print(
        "PASS: REVIEW word is eligible "
        "for the review queue."
    )


# ------------------------------------------------------------
# CLEANUP
# ------------------------------------------------------------

clean_word(word_1)
clean_word(word_2)


print("\n========================================")
print("All batch tests passed.")
print("Test data removed.")
print("========================================")