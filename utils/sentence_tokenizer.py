from sentence_transformers import SentenceTransformer
import numpy as np
import hashlib

# Initialize model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Global token storage
token_dict = {}
token_counter = 0

def Get_token(sentence: str) -> int:
    global token_counter

    # Step 1: Embed sentence
    embedding = model.encode(sentence)

    # Step 2: Round to reduce noise, group similar sentences
    rounded = np.round(embedding, decimals=1)

    # Step 3: Create a hash key from the rounded embedding
    key = hashlib.sha256(rounded.tobytes()).hexdigest()

    # Step 4: Store unique ID for that hash
    if key not in token_dict:
        token_dict[key] = token_counter
        token_counter += 1

    return token_dict[key]