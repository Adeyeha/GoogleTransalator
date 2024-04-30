from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Annotated, List, Union
from fuzzywuzzy import process
from googletrans import Translator 
import os

from dotenv import load_dotenv
load_dotenv()

# Models
class Languages(BaseModel):
    supported: List[str] = Field(description="A list of supported Languages", examples=[["yoruba", "hausa"]])

class Search(BaseModel):
    word: Union[str, None] = Field(None, description="A search word to finds the closest supported languages", examples=["yoruba"])

class UserPromptResponse(BaseModel):
    completion: str = Field(description="AI translated response", examples=["J'mappele Bard"])

class UserPrompt(BaseModel):
    prompt: str = Field(description="String to be translated", examples=["My name is Bard"])
    destination_language: str = Field(description="Destination language for translation", examples=["hausa"])

# FastAPI app initialization
app = FastAPI()

origins = [
    "http://localhost",
    "https://maya-ai-actl.azurewebsites.net",
    "https://maya-actl-services.azurewebsites.net"

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load API key and supported languages from environment variables
api_key = os.getenv('API_KEY')
languages = [x.lower() for x in os.getenv('LANGUAGES').split(",")]
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# Authentication function
async def is_authenticated(api_key_header: str = Depends(api_key_header)) -> bool:
    if not api_key_header == api_key:
        raise HTTPException(
            status_code=401,
            detail="Incorrect Authentication credentials",
        )
    return True

def search_closest_items(search_word, items, threshold=75) -> List:
    try:
        # Use process.extract to find all matches above the threshold
        matches = process.extract(search_word, items)
        
        # Filter out matches below the threshold
        filtered_matches = [match for match, score in matches if score >= threshold]
        
        # Sort filtered_matches in decreasing order based on score
        filtered_matches = sorted(filtered_matches, key=lambda x: matches[filtered_matches.index(x)][1], reverse=True)
        
        return filtered_matches
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )

# Routes
@app.get("/supported_languages", status_code=200, response_model=Languages)
def supported_languages(
    search : Annotated[Union[str,None], "A search word to finds the closest supported languages"],
    auth: bool = Depends(is_authenticated)
):
    try:
        if search:
            # If a search word is provided, return the closest matches
            return Languages(supported=search_closest_items(search, languages))
        
        # If no search word, return all supported languages
        return Languages(supported=languages)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )

@app.get("/all_supported_languages", status_code=200, response_model=Languages)
def all_supported_languages(
    auth: bool = Depends(is_authenticated)
):
    try:
        return Languages(supported=languages)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )

@app.post("/translate", status_code=200, response_model=UserPromptResponse)
def translate(
    userprompt: Annotated[UserPrompt, Body(...)],
    auth: bool = Depends(is_authenticated)
):
    try:
        # Validate destination_language against the list of supported languages
        if userprompt.destination_language.lower() not in languages:
            raise HTTPException(
                status_code=400,
                detail="Invalid destination language. Please provide a valid destination language.",
            )
        translator = Translator()
        out = translator.translate(userprompt.prompt, dest=userprompt.destination_language)
        return UserPromptResponse(completion=out.text)
    except HTTPException as he:
        # Re-raise HTTPException to maintain its status code and detail
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )
