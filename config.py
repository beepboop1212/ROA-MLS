# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- BRANDING & CONSTANTS ---
COMPANY_NAME = "Realty of America"
COMPANY_LOGO_URL = "https://iili.io/FnwmFmF.png"

# --- API ENDPOINTS ---
BANNERBEAR_API_ENDPOINT = "https://api.bannerbear.com/v2"
FREEIMAGE_API_ENDPOINT = "https://freeimage.host/api/1/upload"
# NEW: Added the MLS Search API endpoint
MLS_SEARCH_API_ENDPOINT = "https://staging-v2.realtyofamerica.com/api/mls-search/v1/listings/"

# --- API KEYS ---
BB_API_KEY = os.getenv("BANNERBEAR_API_KEY")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
FREEIMAGE_API_KEY = os.getenv("FREEIMAGE_API_KEY")

# NEW: The mapping from your Bannerbear template layer names to the MLS JSON data paths.
# This is the "secret sauce" that connects the two systems.
# You can easily update this dictionary without changing any other code.
# The value is the "path" to the data in the JSON, using dots for nesting.
MLS_DATA_MAPPING = {
    # Text Layers
    "property_address": "formatted_address",
    "property_price": "price_display",
    "description": "description",
    "bedrooms": "bedrooms",
    "bathrooms": "bathrooms",
    "square_feet": "square_feet",
    "agent_name": "agents.listing_agent.name",
    "agent_contact": "agents.listing_agent.phone",
    "agent_email": "agents.listing_agent.email",
    "neighborhood": "geo_data.neighborhood_name",
    "brokerage_name": "agents.listing_agent.office.name",

    # Image Layers
    # We map to the 'large' version of the hero image.
    "property_image": "hero.large",
    "agent_photo": None, # Set to None as the MLS API doesn't provide this. The bot will ask for it.

    # Example of mapping to the 2nd photo in the gallery if needed
    # "secondary_photo": "photos.1.large"
}

#12401607