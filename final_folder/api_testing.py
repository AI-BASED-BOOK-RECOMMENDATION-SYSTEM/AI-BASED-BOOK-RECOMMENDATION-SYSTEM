import os
import re
import requests
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document

from langchain_community.vectorstores import FAISS
from langchain_huggingface import (
    HuggingFaceEmbeddings,
    HuggingFaceEndpoint,
    ChatHuggingFace
)

faiss_context = ""
faiss_response = None
google_response = None
precision = mrr = relevant_count = 0
avg_judge_score = 0
judge_results = []


load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")


st.set_page_config(page_title="AI Book Recommendation", layout="wide")
st.title("📚 AI Book Recommendation System")


def google_books_search_with_fallback(query, max_results=5):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": query, "maxResults": max_results, "key": GOOGLE_API_KEY}
    response = requests.get(url, params=params)

    books = []
    if response.status_code != 200:
        return books

    for item in response.json().get("items", []):
        info = item.get("volumeInfo", {})
        books.append({
            "title": info.get("title", "Not Available"),
            "author": ", ".join(info.get("authors", ["Not Available"])),
            "rating": info.get("averageRating", "Not Available"),
            "description": info.get("description", "Not Available"),
            "link": info.get("infoLink", "Not Available")
        })
    return books


@st.cache_data
def load_data():
    return pd.read_csv("processed_data.csv")

df = load_data()


@st.cache_data
def prepare_documents(df):
    docs = []
    for _, row in df.iterrows():
        text = f"{row['Title']} {row['Author']} {row['Genres']} {row['Description']}"
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "title": row["Title"],
                    "author": row["Author"],
                    "genres": row["Genres"],
                    "rating": row["Avg_Rating"],
                    "num_ratings": row["Num_Ratings"],
                    "num_reviews": row["Num_Reviews"],
                    "book_url": row.get("Book_URL", "Not Available")
                }
            )
        )
    return docs

documents = prepare_documents(df)


@st.cache_resource
def load_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

embedding_model = load_embeddings()


faiss_path = Path("book_vectorstore_local.faiss")

@st.cache_resource
def load_vectorstore():
    if faiss_path.exists():
        return FAISS.load_local(
            faiss_path,
            embedding_model,
            allow_dangerous_deserialization=True
        )
    store = FAISS.from_documents(documents, embedding_model)
    store.save_local(faiss_path)
    return store

vector_store = load_vectorstore()


@st.cache_resource
def load_llm():
    endpoint = HuggingFaceEndpoint(
        repo_id="meta-llama/Llama-3.1-8B-Instruct",
        task="text-generation",
        max_new_tokens=600,
        temperature=0.7,
        huggingfacehub_api_token=HF_TOKEN
    )
    return ChatHuggingFace(llm=endpoint)

chat_model = load_llm()


def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()

def is_relevant(doc, query):
    q = normalize_text(query)
    title = normalize_text(doc.metadata.get("title", ""))
    author = normalize_text(doc.metadata.get("author", ""))
    content = normalize_text(doc.page_content)

   
    if q in title:
        return True

    
    if q in author and q not in title:
        return False

   
    q_tokens = set(q.split())
    doc_tokens = set((title + " " + content).split())
    return len(q_tokens & doc_tokens) >= max(1, len(q_tokens) // 2)

def evaluate_retrieval(results, query, k=5):
    retrieved = [doc for doc, _ in results[:k]]
    relevant = [doc for doc in retrieved if is_relevant(doc, query)]

    precision = len(relevant) / k if k else 0
    mrr = 0
    for i, doc in enumerate(retrieved):
        if is_relevant(doc, query):
            mrr = 1 / (i + 1)
            break

    return round(precision, 3), round(mrr, 3), len(relevant)




import json

def safe_json_parse(text):
    """
    Extracts first JSON object from LLM output safely
    """
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        return json.loads(match.group())
    except Exception:
        return None


def llm_as_judge(chat_model, query, retrieved_docs):
    results = []

    for doc in retrieved_docs:
        m = doc.metadata

        prompt = f"""
You are a  evaluator for a book recommendation system.

User Query:
{query}

Book:
Title: {m['title']}
Author: {m['author']}
Genres: {m['genres']}
Description:
{doc.page_content}

Rules:
- Title must match for named searches.
- Reject author-only matches.
- emotion also check while matching
-if book related particular topic
-books smilar in some way of user query

Respond ONLY in JSON:
{{"relevant": true/false, "score": 0-1, "reason": "short explanation"}}
"""

        try:
            response = chat_model.invoke(prompt)
            parsed = safe_json_parse(response.content)

            if parsed is None:
                raise ValueError("JSON parsing failed")

            result = {
                "relevant": bool(parsed.get("relevant", False)),
                "score": round(float(parsed.get("score", 0.0)), 3),
                "reason": parsed.get("reason", "No explanation provided")
            }

        except Exception as e:
           
            result = {
                "relevant": False,
                "score": 0.0,
                "reason": "Judge model failed or response invalid"
            }

        results.append(result)

    return results




query = st.text_input("🔍 Search for a book, author, or topic:")

if query:
    with st.spinner("Searching..."):

        
        results = vector_store.similarity_search_with_score(query, k=5)
        precision, mrr, relevant_count = evaluate_retrieval(results, query)

        retrieved_docs = [doc for doc, _ in results]
        judge_results = llm_as_judge(chat_model, query, retrieved_docs)

        avg_judge_score = round(
            sum(j["score"] for j in judge_results) / len(judge_results), 3
        )

  
        faiss_context = ""
        for doc in retrieved_docs:
            m = doc.metadata
            faiss_context += f"""
Title: {m['title']}
Author: {m['author']}
Genres: {m['genres']}
Rating: {m['rating']}
Total Ratings: {m['num_ratings']}
Total Reviews: {m['num_reviews']}
Description: {doc.page_content}
Link: {m['book_url']}
---
"""

        
faiss_prompt = f"""
You are a helpful AI Book Recommendation Assistant.

Your task:
- Understand the user's intent and query.
- Recommend **only relevant books** from the provided CONTEXT.
- Use genre, description, and emotional tone (if query is emotional: e.g., "sad", "motivational", "peaceful").
- If the user asks for a specific book title or a proper name (e.g., "Shivaji Maharaj", "Sachin Tendulkar"), **match the title strictly**.
- Do NOT recommend author-only matches.
- After including all strict matches, if fewer than 5 books, you may add additional books from the CONTEXT that are **closely related in topic or genre** to fill up to 5.

If CONTEXT is empty or not relevant, respond ONLY with:
**"No matching books found for your query."**

Otherwise, produce up to **5 books** using the structured format below.

📘 OUTPUT FORMAT (for EACH BOOK, strictly with line breaks):

----------------------------------------------------
Book {{number}}
**Title:** <Book Title>  
**Author:** <Author Name>  
**Genres:** <Genres>  
**Rating:** <Rating out of 5>  
**Total Ratings:** <Number of Ratings>  
**Total Reviews:** <Number of Reviews>  

**Short Summary:**  
<2–3 line simple summary based on the description or context>

**Why you should read it:**  
<One paragraph explaining the type of reader, emotion/genre, and value of the book>

**Link:**  
<URL if available>
----------------------------------------------------

📘 RULES:
- Bold titles.
- Each field on its own line (do NOT merge).
- Links on a **new line** after "Link:".
- Number each book properly: Book 1, Book 2, …
- If a field is missing, fill logically with "Not Available".
- Show only books **relevant to the query or topic** (max 5).
- Do NOT add extra commentary outside the format.
- Do not show books where all fields are missing.
- **Strict matches first**, then topic-related books if needed to reach 5 books.

📘 CONTEXT (top retrieved books):
{faiss_context}

📘 USER QUESTION:
{query}

Now produce the answer.
"""


faiss_response = chat_model.invoke(faiss_prompt)

        
google_books = google_books_search_with_fallback(query)
google_context = ""
for b in google_books:
        google_context += f"""
Title: {b['title']}
Author: {b['author']}
Rating: {b['rating']}
Description: {b['description']}
Link: {b['link']}
---
"""
google_prompt = f"""
You are a Book Listing Assistant.

Task:
- For each book, generate a 2–3 line summary using description
- Write 'Why you should read it' paragraph explaining the book, reader type, and value
- Include Title, Author, Rating, Description, Link
- If any field missing → write 'Not Available'
- Do NOT invent data beyond given context
- Use simple English and clear formatting
-give only proper book that is available on gogle use links proper try goodreads website
-show 5 books
📘 OUTPUT FORMAT (for EACH BOOK, strictly with line breaks):

----------------------------------------------------
Book {{number}}
**Title:** <Book Title>  
**Author:** <Author Name>  
**Genres:** <Genres>  
**Rating:** <Rating out of 5>  
**Total Ratings:** <Number of Ratings>  
**Total Reviews:** <Number of Reviews>  

**Short Summary:**  
<2–3 line simple summary based on the description or context>

**Why you should read it:**  
<One paragraph explaining the type of reader, emotion/genre, and value of the book>


----------------------------------------------------

Context:
{google_context}

User Query:
{query}

Answer:
"""

google_response = chat_model.invoke(google_prompt)

# ------------------------------
# 11. DISPLAY RESULTS
# ------------------------------
# st.subheader("📊 RAG Evaluation Metrics")
# st.metric("Precision@5", precision)
# st.metric("MRR", mrr)
# st.metric("Relevant Books", f"{relevant_count} / 5")

# st.subheader("🧠 LLM-as-Judge")
# st.metric("Avg Relevance Score", avg_judge_score)

# with st.expander("Judge Decisions"):
#     for i, j in enumerate(judge_results, 1):
#         st.write(f"Book {i} → Relevant: {j['relevant']} | Score: {j['score']}")
#         st.caption(j["reason"])

st.subheader("📘 Books Recommendations")
st.write(faiss_response.content)

st.subheader("🌐 Google Books")
st.write(google_response.content)
