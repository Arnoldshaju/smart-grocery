import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer

# Load product catalog
df = pd.read_csv("orders.csv").fillna("")

# Create combined text field
df['text'] = (
    df['ProductName'] + " " +
    df['Brand'] + " " +
    df['Category'] + " " +
    df['SubCategory']
)

# Train TF-IDF
vectorizer = TfidfVectorizer(stop_words='english')
tfidf_matrix = vectorizer.fit_transform(df['text'])

# Save model
pickle.dump(vectorizer, open("vectorizer.pkl", "wb"))
pickle.dump(tfidf_matrix, open("tfidf_matrix.pkl", "wb"))
pickle.dump(df, open("products.pkl", "wb"))

print("✅ Similarity model trained")
