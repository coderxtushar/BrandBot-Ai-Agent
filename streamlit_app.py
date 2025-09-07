# streamlit_app.py

import streamlit as st
from backend.agent_core import full_agent_graph

# --- Page Configuration ---
st.set_page_config(page_title="LinkedIn Branding AI", page_icon="🤖")

# --- Application Header ---
st.title("Autonomous LinkedIn Personal Branding AI Agent 🤖")
st.markdown("<h3 style='text-align: center; color: grey;'>The complete AI toolkit for strategy, research, and content creation.</h3>", unsafe_allow_html=True)
st.markdown("---")

# --- The User Input Form ---
with st.form(key='branding_form'):
    st.subheader("Step 1: Define Your Personal Brand")
    
    target_audience = st.text_input("Who is your target audience?", placeholder="e.g., Startup founders, senior software engineers")
    expertise = st.text_input("What are your main areas of expertise?", placeholder="e.g., AI development, digital marketing")
    tone_of_voice = st.text_area("Describe your desired tone of voice.", placeholder="e.g., Technical and informative, inspirational and witty")
    content_pillars = st.text_area("List 3-5 content pillars (key themes).", placeholder="e.g., AI in healthcare, Python tips, career growth")
    linkedin_url = st.text_input("What is your LinkedIn profile URL?", placeholder="https://linkedin.com/in/your-profile")

    submitted = st.form_submit_button("Run Full AI Workflow")

# --- Processing and Displaying the Output ---
if submitted:
    if not all([target_audience, expertise, tone_of_voice, content_pillars, linkedin_url]):
        st.error("Please fill out all the fields to run the AI agent.")
    else:
        with st.spinner("🤖 AI assembly line is running... This may take a moment..."):
            
            user_input = {
                "target_audience": target_audience,
                "expertise": expertise,
                "tone_of_voice": tone_of_voice,
                "content_pillars": content_pillars,
                "linkedin_url": linkedin_url
            }
            initial_state = {"brand_info": user_input}

            # We call our final, full agent graph
            final_state = full_agent_graph.invoke(initial_state)
            
            # --- Display the Brand Profile ---
            st.subheader("🚀 Your AI-Generated Brand Profile")
            brand_profile = final_state.get("brand_profile", "Error: No profile was generated.")
            with st.expander("View Brand Profile"):
                st.markdown(brand_profile)
            
            # --- Display the Research Results ---
            st.subheader("🔍 Your AI-Powered Content Research")
            research_results = final_state.get("search_results", "No research was conducted.")
            with st.expander("View Research Results"):
                st.text_area("Research Details", research_results, height=300)
            
            # --- Display the Final, Reviewed LinkedIn Posts ---
            st.subheader("✍️ Your Approved LinkedIn Posts")
            st.info("These posts have been reviewed by a compliance AI to ensure professionalism and ethical alignment.")
            
            reviewed_posts = final_state.get("reviewed_posts", "No posts were generated or reviewed.")
            
            st.markdown(reviewed_posts)
            st.success("Your AI workflow is complete!")