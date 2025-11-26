import spacy
import pandas as pd

nlp = spacy.load("en_core_web_sm")
data = pd.read_csv("C:/Users/Asus/Desktop/cdac/project/AI-BASED-BOOK-RECOMMENDATION-SYSTEM/Data/processed data/processed_data.csv")

data['text'] = data['Title'] + ' ' + data['Author'] + ' ' + data['Genres'] + ' ' + data['Description']

def preprocess_text(text):
    doc = nlp(text.lower())
    tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct]
    return " ".join(tokens)

data['clean_text'] = data['text'].apply(preprocess_text)

data.to_csv("C:/Users/Asus/Desktop/cdac/project/AI-BASED-BOOK-RECOMMENDATION-SYSTEM/Data/clean_and_lemmatize_data/clean_and_lemmatize_data.csv", index=False)