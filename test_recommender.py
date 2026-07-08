from grocery_app.ml_models.recommender import recommend_products

query = "Milk"   # change this for testing

results = recommend_products(query)

print("\n=================================")
print("Smart Grocery Recommender Test")
print("=================================")

print("\nInput:", query)
print("\nRecommendations:\n")

if not results:
    print("No recommendations found.")
else:
    for r in results:
        print(f"{r['ProductName']} | Score: {round(r['score'],3)}")