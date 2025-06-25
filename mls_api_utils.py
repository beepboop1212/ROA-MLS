# mls_api_utils.py
import requests
import logging
from typing import Optional, Dict, Any

from config import MLS_SEARCH_API_ENDPOINT

logger = logging.getLogger(__name__)

# NEW: Define the MLS system ID as a constant.
# If you ever need to support more, you can change it here.
TARGET_MLS_SYSTEM_ID = 386

def get_from_nested_dict(data_dict: Dict, key_path: str) -> Optional[Any]:
    """
    Safely retrieves a value from a nested dictionary using a dot-separated key path.
    Example: get_from_nested_dict(data, 'agents.listing_agent.name')
    """
    keys = key_path.split('.')
    current_level = data_dict
    for key in keys:
        if isinstance(current_level, dict):
            current_level = current_level.get(key)
        elif isinstance(current_level, list):
            try:
                idx = int(key)
                if 0 <= idx < len(current_level):
                    current_level = current_level[idx]
                else:
                    return None
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current_level

def fetch_listing_by_mls_id(mls_listing_id: str) -> Optional[Dict]:
    """
    Fetches a single listing from the MLS Search API using its MLS Listing ID.

    Returns:
        The 'listing' object dictionary on success, None on failure.
    """
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    payload = {
        "size": 1,
        # THE FIX: Added the mandatory 'mlses' parameter.
        "mlses": [TARGET_MLS_SYSTEM_ID],
        "mls_listings": [mls_listing_id],
        "view": "detailed"
    }

    try:
        logger.info(f"Fetching MLS data for ID: {mls_listing_id} from MLS system {TARGET_MLS_SYSTEM_ID}")
        response = requests.post(MLS_SEARCH_API_ENDPOINT, headers=headers, json=payload, timeout=20)
        response.raise_for_status()

        data = response.json()
        
        if data.get("status") == "success" and data.get("data", {}).get("total_elements", 0) > 0:
            listing = data["data"]["content"]["listings"][0]
            logger.info(f"Successfully fetched listing: {listing.get('formatted_address')}")
            return listing
        else:
            logger.warning(f"MLS API returned success, but no listing found for ID: {mls_listing_id}")
            return None

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching MLS data: {e}. Response body: {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection or timeout error fetching MLS data: {e}")
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected JSON structure from MLS API: {e}")

    return None