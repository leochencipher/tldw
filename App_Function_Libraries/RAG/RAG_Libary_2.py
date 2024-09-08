# RAG_Library_2.py
# Description: This script contains the main RAG pipeline function and related functions for the RAG pipeline.
#
# Import necessary modules and functions
import configparser
import logging
import os
from typing import Dict, Any, List, Optional
# Local Imports
from App_Function_Libraries.RAG.ChromaDB_Library import process_and_store_content, vector_search, chroma_client
from App_Function_Libraries.Article_Extractor_Lib import scrape_article
from App_Function_Libraries.DB.DB_Manager import add_media_to_database, search_db, get_unprocessed_media, \
    fetch_keywords_for_media
# 3rd-Party Imports
import openai
#
########################################################################################################################
#
# Functions:

# Initialize OpenAI client (adjust this based on your API key management)
openai.api_key = "your-openai-api-key"

# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the config file
config_path = os.path.join(current_dir, 'Config_Files', 'config.txt')
# Read the config file
config = configparser.ConfigParser()
# Read the configuration file
config.read('config.txt')

# Main RAG pipeline function
def rag_pipeline(url: str, query: str, api_choice=None) -> Dict[str, Any]:
    try:
        # Extract content
        try:
            article_data = scrape_article(url)
            content = article_data['content']
            title = article_data['title']
        except Exception as e:
            logging.error(f"Error scraping article: {str(e)}")
            return {"error": "Failed to scrape article", "details": str(e)}

        # Store the article in the database and get the media_id
        try:
            media_id = add_media_to_database(url, title, 'article', content)
        except Exception as e:
            logging.error(f"Error adding article to database: {str(e)}")
            return {"error": "Failed to store article in database", "details": str(e)}

        # Process and store content
        collection_name = f"article_{media_id}"
        try:
            process_and_store_content(content, collection_name, media_id)
        except Exception as e:
            logging.error(f"Error processing and storing content: {str(e)}")
            return {"error": "Failed to process and store content", "details": str(e)}

        # Perform searches
        try:
            vector_results = vector_search(collection_name, query, k=5)
            fts_results = search_db(query, ["content"], "", page=1, results_per_page=5)
        except Exception as e:
            logging.error(f"Error performing searches: {str(e)}")
            return {"error": "Failed to perform searches", "details": str(e)}

        # Combine results with error handling for missing 'content' key
        all_results = []
        for result in vector_results + fts_results:
            if isinstance(result, dict) and 'content' in result:
                all_results.append(result['content'])
            else:
                logging.warning(f"Unexpected result format: {result}")
                all_results.append(str(result))

        context = "\n".join(all_results)

        # Generate answer using the selected API
        try:
            answer = generate_answer(api_choice, context, query)
        except Exception as e:
            logging.error(f"Error generating answer: {str(e)}")
            return {"error": "Failed to generate answer", "details": str(e)}

        return {
            "answer": answer,
            "context": context
        }

    except Exception as e:
        logging.error(f"Unexpected error in rag_pipeline: {str(e)}")
        return {"error": "An unexpected error occurred", "details": str(e)}


def generate_answer(api_choice: str, context: str, query: str) -> str:
    prompt = f"Context: {context}\n\nQuestion: {query}"
    if api_choice == "OpenAI":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_openai
        return summarize_with_openai(config['API']['openai_api_key'], prompt, "")
    elif api_choice == "Anthropic":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_anthropic
        return summarize_with_anthropic(config['API']['anthropic_api_key'], prompt, "")
    elif api_choice == "Cohere":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_cohere
        return summarize_with_cohere(config['API']['cohere_api_key'], prompt, "")
    elif api_choice == "Groq":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_groq
        return summarize_with_groq(config['API']['groq_api_key'], prompt, "")
    elif api_choice == "OpenRouter":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_openrouter
        return summarize_with_openrouter(config['API']['openrouter_api_key'], prompt, "")
    elif api_choice == "HuggingFace":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_huggingface
        return summarize_with_huggingface(config['API']['huggingface_api_key'], prompt, "")
    elif api_choice == "DeepSeek":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_deepseek
        return summarize_with_deepseek(config['API']['deepseek_api_key'], prompt, "")
    elif api_choice == "Mistral":
        from App_Function_Libraries.Summarization_General_Lib import summarize_with_mistral
        return summarize_with_mistral(config['API']['mistral_api_key'], prompt, "")
    elif api_choice == "Local-LLM":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_local_llm
        return summarize_with_local_llm(config['API']['local_llm_path'], prompt, "")
    elif api_choice == "Llama.cpp":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_llama
        return summarize_with_llama(config['API']['llama_api_key'], prompt, "")
    elif api_choice == "Kobold":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_kobold
        return summarize_with_kobold(config['API']['kobold_api_key'], prompt, "")
    elif api_choice == "Ooba":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_oobabooga
        return summarize_with_oobabooga(config['API']['ooba_api_key'], prompt, "")
    elif api_choice == "TabbyAPI":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_tabbyapi
        return summarize_with_tabbyapi(config['API']['tabby_api_key'], prompt, "")
    elif api_choice == "vLLM":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_vllm
        return summarize_with_vllm(config['API']['vllm_api_key'], prompt, "")
    elif api_choice == "ollama":
        from App_Function_Libraries.Local_Summarization_Lib import summarize_with_ollama
        return summarize_with_ollama(config['API']['ollama_api_key'], prompt, "")
    else:
        raise ValueError(f"Unsupported API choice: {api_choice}")

# Function to preprocess and store all existing content in the database
def preprocess_all_content():
    unprocessed_media = get_unprocessed_media()
    for row in unprocessed_media:
        media_id = row[0]
        content = row[1]
        media_type = row[2]
        collection_name = f"{media_type}_{media_id}"
        process_and_store_content(content, collection_name, media_id)


# Function to perform RAG search across all stored content
def rag_search(query: str, api_choice: str, keywords: str = "") -> Dict[str, Any]:
    keyword_list = [k.strip().lower() for k in keywords.split(',')] if keywords else []

    all_collections = chroma_client.list_collections()
    vector_results = []
    for collection in all_collections:
        vector_results.extend(vector_search(collection.name, query, k=2))

    fts_results = search_db(query, ["content"], "", page=1, results_per_page=10)

    # Combine vector and FTS results
    all_results = vector_results + [{"content": result['content'], "metadata": {"media_id": result['id']}} for result in fts_results]

    # Filter results based on keywords
    filtered_results = filter_results_by_keywords(all_results, keyword_list)

    # Extract content from filtered results
    context_texts = [result['content'] for result in filtered_results[:10]]  # Limit to top 10 results
    context = "\n".join(context_texts)

    # Generate answer using the selected API
    answer = generate_answer(api_choice, context, query)

    return {
        "answer": answer,
        "context": context
    }


# RAG Search with keyword filtering
def enhanced_rag_pipeline(query: str, api_choice: str, keywords: str = "") -> Dict[str, Any]:
    try:
        # Process keywords
        keyword_list = [k.strip().lower() for k in keywords.split(',')] if keywords else []

        # Fetch relevant media IDs based on keywords
        relevant_media_ids = fetch_relevant_media_ids(keyword_list) if keyword_list else None

        # Perform vector search with keyword filtering
        all_collections = chroma_client.list_collections()
        vector_results = []
        for collection in all_collections:
            collection_results = vector_search(collection.name, query, k=5)
            filtered_results = [
                result for result in collection_results
                if relevant_media_ids is None or result['metadata'].get('media_id') in relevant_media_ids
            ]
            vector_results.extend(filtered_results)

        # Perform full-text search with keyword filtering
        fts_results = search_db(query, ["content"], "", page=1, results_per_page=5)
        filtered_fts_results = [
            result for result in fts_results
            if relevant_media_ids is None or result['id'] in relevant_media_ids
        ]

        # Combine results
        all_results = vector_results + [
            {
                "content": result['content'],
                "metadata": {"media_id": result['id']}
            } for result in filtered_fts_results
        ]

        if not all_results:
            logging.info(f"No results found. Query: {query}, Keywords: {keywords}")
            return {
                "answer": "I couldn't find any relevant information based on your query and keywords.",
                "context": ""
            }

        # Extract content from results
        context_texts = [result['content'] for result in all_results[:10]]  # Limit to top 10 results
        context = "\n".join(context_texts)

        # Generate answer using the selected API
        answer = generate_answer(api_choice, context, query)

        return {
            "answer": answer,
            "context": context
        }
    except Exception as e:
        logging.error(f"Error in enhanced_rag_pipeline: {str(e)}")
        return {
            "answer": "An error occurred while processing your request.",
            "context": ""
        }


def fetch_relevant_media_ids(keywords: List[str]) -> List[int]:
    relevant_ids = set()
    try:
        for keyword in keywords:
            media_ids = fetch_keywords_for_media(keyword)
            relevant_ids.update(media_ids)
    except Exception as e:
        logging.error(f"Error fetching relevant media IDs: {str(e)}")
    return list(relevant_ids)


def filter_results_by_keywords(results: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not keywords:
        return results

    filtered_results = []
    for result in results:
        try:
            metadata = result.get('metadata', {})
            if not isinstance(metadata, dict):
                logging.warning(f"Unexpected metadata type: {type(metadata)}. Expected dict.")
                continue

            media_id = metadata.get('media_id')
            if media_id is None:
                logging.warning(f"No media_id found in metadata: {metadata}")
                continue

            media_keywords = fetch_keywords_for_media(media_id)
            if any(keyword.lower() in [mk.lower() for mk in media_keywords] for keyword in keywords):
                filtered_results.append(result)
        except Exception as e:
            logging.error(f"Error processing result: {result}. Error: {str(e)}")

    return filtered_results

# FIXME: to be implememted
def extract_media_id_from_result(result: str) -> Optional[int]:
    # Implement this function based on how you store the media_id in your results
    # For example, if it's stored at the beginning of each result:
    try:
        return int(result.split('_')[0])
    except (IndexError, ValueError):
        logging.error(f"Failed to extract media_id from result: {result}")
        return None




# Example usage:
# 1. Initialize the system:
# create_tables(db)  # Ensure FTS tables are set up
#
# 2. Create ChromaDB
# chroma_client = ChromaDBClient()
#
# 3. Create Embeddings
# Store embeddings in ChromaDB
# preprocess_all_content() or create_embeddings()
#
# 4. Perform RAG search across all content:
# result = rag_search("What are the key points about climate change?")
# print(result['answer'])
#
# (Extra)5. Perform RAG on a specific URL:
# result = rag_pipeline("https://example.com/article", "What is the main topic of this article?")
# print(result['answer'])
#
########################################################################################################################


############################################################################################################
#
# ElasticSearch Retriever

# https://github.com/langchain-ai/langchain/tree/44e3e2391c48bfd0a8e6a20adde0b6567f4f43c3/templates/rag-elasticsearch
#
# https://github.com/langchain-ai/langchain/tree/44e3e2391c48bfd0a8e6a20adde0b6567f4f43c3/templates/rag-self-query

#
# End of RAG_Library_2.py
############################################################################################################
