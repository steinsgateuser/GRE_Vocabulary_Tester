import os
import re
from collections import Counter

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(BASE_DIR, "Vocabulary_KB.xlsx")

polo_words = '''
Castigate, Lambaste, Vituperate, Berate, Excoriate, Chastise, Rebuke, Upbraid
'''

# ---------------------------------------------------------------------------
# Word normalization
# ---------------------------------------------------------------------------

def normalize_word(word):
    return re.sub(r"[^a-z]", "", str(word).lower())


# ---------------------------------------------------------------------------
# Selected words for Level 1
# ---------------------------------------------------------------------------

def get_selected_words():
    """Words from `polo_words` that appear exactly once (deduplicated set)."""
    words = [normalize_word(w) for w in re.findall(r"[A-Za-z]+", polo_words)]
    counts = Counter(words)

    return {word for word in words if counts[word] == 1}


# ---------------------------------------------------------------------------
# Load vocabulary
# ---------------------------------------------------------------------------

def load_vocab():
    df = pd.read_excel(EXCEL_PATH, sheet_name=0)

    # Remove completely empty columns
    df = df.dropna(axis=1, how="all")

    # First row contains column names; promote it, then drop it
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    df.columns = ["Cluster", "Idx", "Word", "Connotation", "Example / Mnemonics"]

    # Fill cluster names downward
    df["Cluster"] = df["Cluster"].ffill()

    # Remove completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # Clean Word: extract individual words, title-cased
    df["Word"] = df["Word"].apply(
        lambda text: [w.title() for w in re.findall(r"[A-Za-z]+", str(text))]
    )

    # One word per row
    df = df.explode("Word").reset_index(drop=True)

    # Remove NaN / empty values
    df = df.dropna(subset=["Word", "Connotation"])

    df["Word"] = df["Word"].astype(str).str.strip()
    df["Connotation"] = df["Connotation"].astype(str).str.strip()

    # Remove literal "nan"
    df = df[
        (df["Word"] != "")
        & (df["Word"].str.lower() != "nan")
        & (df["Connotation"].str.lower() != "nan")
    ]

    # Normalized word for matching
    df["Word_Normalized"] = df["Word"].apply(normalize_word)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Get vocabulary data
# ---------------------------------------------------------------------------

def get_vocab_data():
    df = load_vocab()

    # Level 1: restrict to the selected word set
    selected_words = get_selected_words()
    level_1_df = df[df["Word_Normalized"].isin(selected_words)].copy()

    # Level 2: full vocabulary
    level_2_df = df.copy()

    return df, level_1_df, level_2_df


# ---------------------------------------------------------------------------
# Load data / debug info
# ---------------------------------------------------------------------------

df, level_1_df, level_2_df = get_vocab_data()

print(f"Total vocabulary: {len(level_2_df)} rows")
print(f"Level 1 vocabulary: {len(level_1_df)} rows")