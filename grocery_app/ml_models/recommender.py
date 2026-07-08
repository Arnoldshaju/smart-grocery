"""
Django-Ready Robust Recommender
--------------------------------
- Auto builds pickles if missing
- Safe for Django import
- Returns list of dictionaries (JSON serializable)
"""

import os
import re
import pickle
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity

try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False


# --------------------------
# CONFIG
# --------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_PATH = os.path.join(BASE_DIR, "orders.csv")
PKL_PRODUCTS = os.path.join(BASE_DIR, "products.pkl")
PKL_VECT = os.path.join(BASE_DIR, "vectorizer.pkl")
PKL_TFIDF = os.path.join(BASE_DIR, "tfidf_matrix.pkl")

TOP_N_DEFAULT = 8
ALPHA_RELEV = 0.85
TFIDF_MAX_FEATURES = 20000


# --------------------------
# UTILITIES
# --------------------------
def clean_text(s):
    if pd.isna(s):
        return ""
    s = str(s).lower()
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# --------------------------
# BUILD / LOAD
# --------------------------
def build_pickles():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError("orders.csv not found")

    df = pd.read_csv(CSV_PATH).fillna("")

    for c in ['ProductName','Brand','Category','SubCategory','Sold']:
        if c not in df.columns:
            df[c] = ""

    df['clean_name'] = df['ProductName'].apply(clean_text)
    df['clean_brand'] = df['Brand'].apply(clean_text)
    df['clean_cat'] = df['Category'].apply(clean_text)
    df['clean_subcat'] = df['SubCategory'].apply(clean_text)

    df['text_for_tfidf'] = (
        df['clean_name'] + " " +
        df['clean_brand'] + " " +
        df['clean_cat'] + " " +
        df['clean_subcat']
    ).str.strip()

    df['Sold'] = pd.to_numeric(df['Sold'], errors='coerce').fillna(0.0)

    vectorizer = TfidfVectorizer(
        ngram_range=(1,2),
        max_features=TFIDF_MAX_FEATURES,
        stop_words='english'
    )

    tfidf_matrix = vectorizer.fit_transform(df['text_for_tfidf'])

    pickle.dump(df, open(PKL_PRODUCTS, "wb"))
    pickle.dump(vectorizer, open(PKL_VECT, "wb"))
    pickle.dump(tfidf_matrix, open(PKL_TFIDF, "wb"))

    return df, vectorizer, tfidf_matrix


def load_or_build():
    if os.path.exists(PKL_PRODUCTS) and os.path.exists(PKL_VECT) and os.path.exists(PKL_TFIDF):
        try:
            df = pickle.load(open(PKL_PRODUCTS, "rb"))
            vectorizer = pickle.load(open(PKL_VECT, "rb"))
            tfidf_matrix = pickle.load(open(PKL_TFIDF, "rb"))
            return df, vectorizer, tfidf_matrix
        except Exception:
            return build_pickles()
    else:
        return build_pickles()


# Load once (important for performance)
df, VECT, TFIDF = load_or_build()

sold_scaler = MinMaxScaler()
sold_scaler.fit(df[['Sold']].values)


# --------------------------
# MAIN FUNCTION FOR DJANGO
# --------------------------
def recommend_products(product_name, top_n=TOP_N_DEFAULT):
    """
    Returns list of dictionaries (JSON serializable)
    Safe to use inside Django views
    """

    if not product_name:
        return []

    q = clean_text(product_name)

    # find anchor
    matches = df[df['clean_name'].str.contains(q, na=False)]

    if matches.empty:
        q_vec = VECT.transform([q])
        sims = cosine_similarity(q_vec, TFIDF).flatten()
        best_idx = int(np.argmax(sims))
    else:
        best_idx = matches.index[0]

    anchor_vec = TFIDF[best_idx]
    anchor_cat = df.loc[best_idx, 'Category']

    candidates = df[df['Category'] == anchor_cat].copy()
    candidates = candidates[candidates.index != best_idx]

    if candidates.empty:
        return []

    cand_matrix = TFIDF[candidates.index]
    relevances = cosine_similarity(anchor_vec, cand_matrix).flatten()

    relev_norm = (relevances - relevances.min()) / (
        (relevances.max() - relevances.min()) + 1e-9
    )

    sold_scaled = sold_scaler.transform(
        candidates[['Sold']].values
    ).flatten()

    combined = ALPHA_RELEV * relev_norm + (1 - ALPHA_RELEV) * sold_scaled

    candidates['score'] = combined

    result = candidates.sort_values(
        by='score', ascending=False
    ).head(top_n)

    # 🔥 IMPORTANT: Convert to JSON safe output
    return result[[
        'ProductName',
        'Brand',
        'Category',
        'SubCategory',
        'score'
    ]].to_dict(orient='records')