import streamlit as st
import pandas as pd
from qdrant_client import models, QdrantClient
from sentence_transformers import SentenceTransformer
from openai import OpenAI


@st.cache_resource
def load_data_and_model():
    df = pd.read_csv('countries.csv')
    df = df[df['country'].notna()]
    data = df.to_dict('records')
    encoder = SentenceTransformer('all-MiniLm-L6-v2')
    qdrant = QdrantClient(":memory:")

    qdrant.recreate_collection(
        collection_name="countries",
        vectors_config=models.VectorParams(
            size=encoder.get_sentence_embedding_dimension(),
            distance=models.Distance.COSINE
        )
    )
    qdrant.upload_points(
        collection_name="countries",
        points=[
            models.PointStruct(
                id=idx,
                vector=encoder.encode(doc["description"]).tolist(),
                payload=doc,
            ) for idx, doc in enumerate(data)
        ]
    )
    return data, encoder, qdrant

@st.cache_resource
def init_openai_client():
    return OpenAI(
        base_url="http://192.168.1.8:8080/v1",
        api_key="sk-no-key-required"
    )

# Load data and models
data, encoder, qdrant = load_data_and_model()
client = init_openai_client()


st.title("Geography Assistant : Country Information Search")

user_prompt = st.text_input("Enter a country name or description:")

if user_prompt:
    with st.spinner("Searching..."):
        # Search in Qdrant for the top 3 matching countries
        hits = qdrant.search(
            collection_name="countries",
            query_vector=encoder.encode(user_prompt).tolist(),
            limit=3
        )
        if hits:
            st.subheader("Top 3 matching countries:")
            for i, hit in enumerate(hits, 1):
                country = hit.payload.get("country", "Unknown")
                capital = hit.payload.get("capital", "")
                continent = hit.payload.get("continent", "")
                description = hit.payload.get("description", "")
                st.markdown(f"**{i}. {country}** — *{capital}*, {continent}")
                st.write(description)
        else:
            st.write("No matches found.")

    with st.spinner("Generating response from language model..."):
        completion = client.chat.completions.create(
            model="LLaMA_CPP",
            messages=[
                {"role": "system", "content": "You are a helpful geography assistant. When the user gives you the name of a country, respond with useful and interesting information about that country. Do not recommend other countries."},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
        )
        st.subheader("Assistant's Response:")
        st.write(completion.choices[0].message.content)
