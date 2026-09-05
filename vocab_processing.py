import os
import re

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(BASE_DIR, "Vocabulary_KB.xlsx")


def normalize_word(word):
    return re.sub(r"[^a-z]", "", str(word).lower())


def load_vocab():
    df = pd.read_excel(EXCEL_PATH, sheet_name=0)

    df = df.dropna(axis=1, how="all")

    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    df.columns = [
        "Cluster",
        "Idx",
        "Word",
        "Connotation",
        "Example / Mnemonics"
    ]

    df["Cluster"] = df["Cluster"].ffill()

    df = df.dropna(how="all").reset_index(drop=True)

    df["Word"] = df["Word"].apply(
        lambda text: [
            w.title()
            for w in re.findall(r"[A-Za-z]+", str(text))
        ]
    )

    df = df.explode("Word").reset_index(drop=True)

    df = df.dropna(subset=["Word", "Connotation"])

    df["Word"] = df["Word"].astype(str).str.strip()
    df["Connotation"] = df["Connotation"].astype(str).str.strip()

    df = df[
        (df["Word"] != "")
        & (df["Word"].str.lower() != "nan")
        & (df["Connotation"].str.lower() != "nan")
    ]

    df["Word_Normalized"] = df["Word"].apply(normalize_word)

    return df.reset_index(drop=True)


def get_vocab_data():
    return load_vocab()


df = get_vocab_data()

print(f"Total vocabulary: {len(df)} rows")