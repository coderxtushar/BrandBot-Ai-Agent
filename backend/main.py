from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .agent_core import full_agent_graph

app = FastAPI(
    title="LinkedIn Personal Branding AI Agent API",
    description="An API for generating brand profiles, researching topics, and creating LinkedIn posts.",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
   
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


class BrandInfoInput(BaseModel):
    target_audience: str
    expertise: str
    tone_of_voice: str
    content_pillars: str
    linkedin_url: str


@app.get("/")
def read_root():
    return {"status": "LinkedIn AI Agent API is running."}

@app.post("/run-workflow")
async def run_ai_workflow(brand_info: BrandInfoInput):
    """
    This endpoint receives the user's brand information, runs the full AI agent graph,
    and returns the complete result, including the brand profile, research, and posts.
    """
    print("--- Received request to /run-workflow ---")
    

    user_input_dict = brand_info.dict()
    
    initial_state = {"brand_info": user_input_dict}


    final_state = full_agent_graph.invoke(initial_state)

    print("--- AI workflow completed. Sending response. ---")

    return final_state


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)