import os
from typing import TypedDict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langchain_community.tools.tavily_search import TavilySearchResults

from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    brand_info: dict
    brand_profile: str
    search_queries: List[str]
    search_results: Optional[str]
    generated_posts: Optional[str]
    reviewed_posts: Optional[str] 

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
tavily_tool = TavilySearchResults(max_results=3) 
tools = [tavily_tool]
llm_with_tools = llm.bind_tools(tools)


# Node 1: Generate the Brand Profile
def generate_profile_node(state: AgentState):
    """Generates a structured brand profile document based on the user's raw input."""
    print("--- Executing Node: generate_profile_node ---")
    brand_info = state['brand_info']
    prompt = f"""
    **Objective:** Create a comprehensive and structured Personal Brand Profile based on the user's input. The output must be in Markdown format.
    **User's Raw Information:**
    - Target Audience: {brand_info['target_audience']}
    - Areas of Expertise: {brand_info['expertise']}
    - Desired Tone of Voice: {brand_info['tone_of_voice']}
    - Content Pillars: {brand_info['content_pillars']}
    - LinkedIn Profile URL: {brand_info['linkedin_url']}
    **Task:** Generate a Markdown document with the following sections:
    ### 1. Core Brand Identity
    ### 2. Target Audience Persona
    ### 3. Brand Voice & Tone Guidelines
    ### 4. Content Strategy
    ### 5. Hashtag Strategy
    """
    response = llm.invoke(prompt)
    print("--- Brand Profile Generated ---")
    return {"brand_profile": response.content}

# Node 2: The Planner
def planner_node(state: AgentState):
    """Reads the brand profile and generates specific search queries to find timely content."""
    print("--- Executing Node: planner_node ---")
    brand_profile = state['brand_profile']
    prompt = f"""
    You are an expert content strategist. Generate 2 specific, actionable search queries based on the provided Brand Profile.
    **Brand Profile:**\n{brand_profile}
    **Instructions:**
    - Focus on the "Content Strategy" and "Content Pillars".
    - Generate specific, high-quality queries.
    - **IMPORTANT**: Your output must be only the Python list of strings.
    **Example Output:**
    ["latest trends in Tableau data visualization for Q3 2025", "common mistakes in machine learning projects for beginners"]
    """
    response = llm.invoke(prompt)
    queries = [q.strip().strip("'\"") for q in response.content.strip('[]').split(',')]
    print(f"--- Generated Search Queries: {queries} ---")
    return {"search_queries": queries}

# Node 3: The Tool User
def tool_user_node(state: AgentState):
    """Takes the search queries and executes them using the Tavily web search tool."""
    print("--- Executing Node: tool_user_node ---")
    queries = state['search_queries']
    search_results = tavily_tool.batch(queries)
    print("--- Search Results Fetched ---")
    results_string = ""
    for query, result in zip(queries, search_results):
        results_string += f"--- Results for query: '{query}' ---\n{result}\n\n"
    return {"search_results": results_string}

# Node 4: The Content Agent
def content_agent_node(state: AgentState):
    """This is the creative writer. It generates 3 distinct LinkedIn posts."""
    print("--- Executing Node: content_agent_node ---")
    brand_profile = state['brand_profile']
    search_results = state['search_results']
    prompt = f"""
    **Objective:** You are an expert LinkedIn ghostwriter. Write 3 distinct and engaging LinkedIn posts based on the Brand Profile and Research Results.
    **1. Master Blueprint: The Brand Profile**
    ---\n{brand_profile}\n---
    **2. Raw Material: The Research Results**
    ---\n{search_results}\n---
    **3. Your Task: Generate 3 LinkedIn Posts**
    **CRITICAL INSTRUCTIONS:**
    - Adhere to the "Brand Voice & Tone Guidelines."
    - Synthesize insights from the research; do not just copy.
    - Each post MUST start with a strong hook and end with an open-ended question.
    - Conclude each post with 3-5 relevant hashtags from the "Hashtag Strategy".
    - Format clearly with separators (---) and whitespace.
    """
    response = llm.invoke(prompt)
    print("--- LinkedIn Posts Generated ---")
    return {"generated_posts": response.content}

# Node 5: The Review Agent
def review_agent_node(state: AgentState):
    """This is the compliance officer. It reviews the posts for professionalism and ethical alignment."""
    print("--- Executing Node: review_agent_node ---")
    generated_posts = state['generated_posts']
    prompt = f"""
    **Objective:** You are a Brand Compliance Manager. Review the provided LinkedIn posts for professionalism, factual soundness, and ethical alignment.
    **Posts to Review:**
    ---\n{generated_posts}\n---
    **Your Task:**
    Review the posts against these criteria: Professional Tone, Unsubstantiated Claims, and Ethical Concerns.
    **CRITICAL INSTRUCTIONS:**
    - **If all posts are compliant:** Return the original text EXACTLY as it was given.
    - **If a post needs a minor correction:** Rewrite only the problematic part and return the full, corrected text.
    Your final output must ONLY be the approved or corrected text of the posts.
    """
    response = llm.invoke(prompt)
    print("--- Posts Have Been Reviewed and Approved ---")
    return {"reviewed_posts": response.content}

# 5. Build the Graph
graph_builder = StateGraph(AgentState)

graph_builder.add_node("generate_profile", generate_profile_node)
graph_builder.add_node("planner", planner_node)
graph_builder.add_node("tool_user", tool_user_node)
graph_builder.add_node("content_agent", content_agent_node)
graph_builder.add_node("review_agent", review_agent_node)

graph_builder.set_entry_point("generate_profile")
graph_builder.add_edge("generate_profile", "planner")
graph_builder.add_edge("planner", "tool_user")
graph_builder.add_edge("tool_user", "content_agent")
graph_builder.add_edge("content_agent", "review_agent")
graph_builder.add_edge("review_agent", END)

full_agent_graph = graph_builder.compile()

print("✅ Full Agent graph compiled successfully with Review Agent.")