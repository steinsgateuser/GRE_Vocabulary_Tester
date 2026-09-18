import os
from contextlib import contextmanager

from dotenv import load_dotenv
import psycopg


load_dotenv(".env.local")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL was not found in .env.local")


@contextmanager
def get_connection():

    conn = psycopg.connect(DATABASE_URL)

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def init_db():

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,
                    word VARCHAR(255) NOT NULL,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    wrong_count INTEGER NOT NULL DEFAULT 0,
                    progress INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'NEW',
                    last_seen TIMESTAMP,
                    UNIQUE(user_id, word)
                )
            """)

            cur.execute("""
                INSERT INTO users (username)
                VALUES ('Polo'), ('Tusu')
                ON CONFLICT (username) DO NOTHING
            """)

    print("Database initialized successfully.")


def migrate_db():

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                ALTER TABLE user_progress
                ADD COLUMN IF NOT EXISTS progress INTEGER
                NOT NULL DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE user_progress
                ADD COLUMN IF NOT EXISTS last_batch INTEGER
                NOT NULL DEFAULT 0
            """)

    print("Database migration completed.")


def get_user_by_username(username):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id, username
                FROM users
                WHERE username = %s
                """,
                (username,)
            )

            row = cur.fetchone()

            if not row:
                return None

            return {
                "id": row[0],
                "username": row[1]
            }


def get_user_progress(user_id):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    word,
                    correct_count,
                    wrong_count,
                    progress,
                    status,
                    last_seen,
                    last_batch
                FROM user_progress
                WHERE user_id = %s
                ORDER BY word
                """,
                (user_id,)
            )

            rows = cur.fetchall()

            return [
                {
                    "word": row[0],
                    "correct_count": row[1],
                    "wrong_count": row[2],
                    "progress": row[3],
                    "status": row[4],
                    "last_seen": row[5],
                    "last_batch": row[6]
                }
                for row in rows
            ]

def record_answer(user_id, word, correct, batch_number):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    correct_count,
                    wrong_count,
                    progress,
                    status
                FROM user_progress
                WHERE user_id = %s
                  AND word = %s
                """,
                (user_id, word)
            )

            row = cur.fetchone()

            # ------------------------------------------------
            # First time seeing this word
            # ------------------------------------------------

            if not row:

                if correct:

                    cur.execute(
                        """
                        INSERT INTO user_progress (
                            user_id,
                            word,
                            correct_count,
                            wrong_count,
                            progress,
                            status,
                            last_seen,
                            last_batch
                        )
                        VALUES (
                            %s,
                            %s,
                            1,
                            0,
                            1,
                            'NEW',
                            NOW(),
                            %s
                        )
                        """,
                        (
                            user_id,
                            word,
                            batch_number
                        )
                    )

                else:

                    cur.execute(
                        """
                        INSERT INTO user_progress (
                            user_id,
                            word,
                            correct_count,
                            wrong_count,
                            progress,
                            status,
                            last_seen,
                            last_batch
                        )
                        VALUES (
                            %s,
                            %s,
                            0,
                            1,
                            0,
                            'REVIEW',
                            NOW(),
                            %s
                        )
                        """,
                        (
                            user_id,
                            word,
                            batch_number
                        )
                    )

                return

            correct_count, wrong_count, progress, status = row

            # ------------------------------------------------
            # MASTERED words stay MASTERED
            # ------------------------------------------------

            if status == "MASTERED":

                cur.execute(
                    """
                    UPDATE user_progress
                    SET last_seen = NOW(),
                        last_batch = %s
                    WHERE user_id = %s
                      AND word = %s
                    """,
                    (
                        batch_number,
                        user_id,
                        word
                    )
                )

                return

            # ------------------------------------------------
            # CORRECT ANSWER
            # ------------------------------------------------

            if correct:

                new_correct_count = (
                    correct_count + 1
                )

                new_progress = progress + 1

                # --------------------------------------------
                # Second consecutive successful learning step
                # --------------------------------------------

                if new_progress >= 2:

                    cur.execute(
                        """
                        UPDATE user_progress
                        SET
                            correct_count = %s,
                            progress = 2,
                            status = 'MASTERED',
                            last_seen = NOW(),
                            last_batch = %s
                        WHERE user_id = %s
                          AND word = %s
                        """,
                        (
                            new_correct_count,
                            batch_number,
                            user_id,
                            word
                        )
                    )

                # --------------------------------------------
                # First successful learning step
                # --------------------------------------------

                else:

                    new_status = (
                        'REVIEW'
                        if status == 'REVIEW'
                        else 'NEW'
                    )

                    cur.execute(
                        """
                        UPDATE user_progress
                        SET
                            correct_count = %s,
                            progress = 1,
                            status = %s,
                            last_seen = NOW(),
                            last_batch = %s
                        WHERE user_id = %s
                          AND word = %s
                        """,
                        (
                            new_correct_count,
                            new_status,
                            batch_number,
                            user_id,
                            word
                        )
                    )

            # ------------------------------------------------
            # WRONG ANSWER / I DON'T KNOW
            # ------------------------------------------------

            else:

                cur.execute(
                    """
                    UPDATE user_progress
                    SET
                        wrong_count = wrong_count + 1,
                        progress = 0,
                        status = 'REVIEW',
                        last_seen = NOW(),
                        last_batch = %s
                    WHERE user_id = %s
                      AND word = %s
                    """,
                    (
                        batch_number,
                        user_id,
                        word
                    )
                )

def get_dashboard_stats(user_id, total_words):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'MASTERED'
                    ),
                    COUNT(*) FILTER (
                        WHERE status = 'REVIEW'
                    ),
                    COUNT(*) FILTER (
                        WHERE status = 'NEW'
                    )
                FROM user_progress
                WHERE user_id = %s
                """,
                (user_id,)
            )

            row = cur.fetchone()

    mastered = row[0] or 0
    review = row[1] or 0

    new_words = total_words - mastered - review

    if total_words > 0:

        mastered_pct = mastered / total_words * 100
        review_pct = review / total_words * 100
        new_pct = new_words / total_words * 100

    else:

        mastered_pct = 0
        review_pct = 0
        new_pct = 0

    return {
        "total": total_words,
        "mastered": mastered,
        "review": review,
        "new": new_words,
        "mastered_pct": round(mastered_pct, 1),
        "review_pct": round(review_pct, 1),
        "new_pct": round(new_pct, 1)
    }


def get_review_words(user_id):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    word,
                    progress,
                    correct_count,
                    wrong_count,
                    last_seen
                FROM user_progress
                WHERE user_id = %s
                  AND status = 'REVIEW'
                ORDER BY last_seen ASC NULLS FIRST
                """,
                (user_id,)
            )

            rows = cur.fetchall()

            return [
                {
                    "word": row[0],
                    "progress": row[1],
                    "correct_count": row[2],
                    "wrong_count": row[3],
                    "last_seen": row[4]
                }
                for row in rows
            ]


def get_queue_counts(user_id):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'REVIEW'
                    ),
                    COUNT(*) FILTER (
                        WHERE status = 'NEW'
                          AND progress = 1
                    )
                FROM user_progress
                WHERE user_id = %s
                """,
                (user_id,)
            )

            row = cur.fetchone()

    return {
        "review": row[0] or 0,
        "validation": row[1] or 0
    }


if __name__ == "__main__":
    init_db()
    migrate_db()