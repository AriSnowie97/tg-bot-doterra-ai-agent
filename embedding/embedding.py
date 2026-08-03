# Standard
import os
import json
# Special
import psycopg2
from google import genai
from pgvector.psycopg2 import register_vector
# Local


# DATABASE_URL = os.getenv("DATABASE_URL", "")

# # Railway іноді повертає postgres:// замість postgresql:// — виправляємо
# if DATABASE_URL.startswith("postgres://"):
#     DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# conn = psycopg2.connect(DATABASE_URL)
# register_vector(conn)

GEMINI_API_KEY_1 = os.getenv("GEMINI_API_KEY_1", "")
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "")
GEMINI_API_KEY_3 = os.getenv("GEMINI_API_KEY_3", "")

ks = [
    GEMINI_API_KEY_1,
    GEMINI_API_KEY_2,
    GEMINI_API_KEY_3
]

client = genai.Client(api_key=ks[2])

chunks = []

# with conn.cursor() as cur:
# for chunk in chunks:
#     response = client.embeddings.create(
#         model="text-embedding-004",
#         input=chunk
#     )

#     embedding = response.data[0].embedding

        # cur.execute(
        #     """
            
        #     """
        # )

hh = "Hello, World!"

response = client.models.embed_content(
    model="models/embedding-001",
    contents=hh
)

embedding = response.embeddings[0].values
print(embedding)
