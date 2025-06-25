# api_utils.py
import streamlit as st
import requests
import time
import base64
import logging
import config

logger = logging.getLogger(__name__)

def bb_headers(api_key):
    return {"Authorization": f"Bearer {api_key}"}

@st.cache_resource(show_spinner="Loading design templates...")
def load_all_template_details(_api_key):
    if not _api_key:
        st.error("Bannerbear API Key is missing.", icon="🛑")
        return None
    try:
        summary_response = requests.get(f"{config.BANNERBEAR_API_ENDPOINT}/templates", headers=bb_headers(_api_key), timeout=15)
        summary_response.raise_for_status()
        return [
            requests.get(f"{config.BANNERBEAR_API_ENDPOINT}/templates/{t['uid']}", headers=bb_headers(_api_key)).json()
            for t in summary_response.json() if t and 'uid' in t
        ]
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to the design service: {e}", icon="🚨")
        return None

def create_image_async(api_key, template_uid, modifications):
    payload = {"template": template_uid, "modifications": modifications, "transparent": True}
    try:
        response = requests.post(f"{config.BANNERBEAR_API_ENDPOINT}/images", headers=bb_headers(api_key), json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error creating image: {e}")
        return None

def poll_for_image_completion(api_key, image_object):
    polling_url = image_object.get("self")
    if not polling_url: return None
    for _ in range(30):
        time.sleep(1)
        try:
            response = requests.get(polling_url, headers=bb_headers(api_key))
            response.raise_for_status()
            polled_object = response.json()
            if polled_object.get('status') == 'completed': return polled_object
            if polled_object.get('status') == 'failed':
                logger.error(f"Image generation failed: {polled_object}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API Error polling for image: {e}")
            return None
    return None

def upload_image_to_public_url(api_key, image_bytes):
    if not api_key:
        st.error("Image hosting API key is missing.", icon="❌")
        return None
    try:
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        payload = {"key": api_key, "source": b64_image, "format": "json"}
        response = requests.post(config.FREEIMAGE_API_ENDPOINT, data=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result.get("status_code") == 200 and result.get("image"):
            return result["image"]["url"]
        else:
            logger.error(f"Image hosting service returned an error: {result}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection error during image upload: {e}")
        return None

def get_listing_details_by_mls_id(mls_listing_id: str, mls_id: int = 386):
    search_url = f"{config.ROA_API_ENDPOINT}/listings/"
    search_payload = {"mlses": [mls_id], "mls_listings": [str(mls_listing_id)], "size": 1}
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    try:
        logger.info(f"Searching for MLS ID: {mls_listing_id}")
        search_response = requests.post(search_url, headers=headers, json=search_payload, timeout=15)
        search_response.raise_for_status()
        search_data = search_response.json()
        if search_data.get('data', {}).get('total_elements', 0) == 0:
            logger.warning(f"No listing found for MLS ID {mls_listing_id}")
            return None, "I couldn't find a listing with that MLS ID. Could you please double-check it?"
        listing_summary = search_data['data']['content']['listings'][0]
        listing_uuid = listing_summary.get('id')
        if not listing_uuid:
            logger.error("Listing found but missing internal UUID.")
            return None, "I found the listing, but there was an issue getting its full details. Please try again."
        logger.info(f"Found UUID {listing_uuid}. Fetching full details.")
        detail_url = f"{search_url}{listing_uuid}/"
        detail_response = requests.get(detail_url, headers=headers, timeout=15)
        detail_response.raise_for_status()
        listing_data = detail_response.json().get('data')
        if not listing_data:
            return None, "I was unable to retrieve the complete data for that listing."
        return listing_data, None
    except requests.exceptions.RequestException as e:
        logger.error(f"ROA API Error for listing {mls_listing_id}: {e}")
        return None, "I'm having some trouble connecting to the property database right now. Please try again in a moment."