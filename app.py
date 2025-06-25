# app.py
import streamlit as st
import logging

import config
import api_utils
import ai_core
import mls_api_utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. INITIALIZATION & SESSION STATE ---
def initialize_app():
    """Sets up the Streamlit page and initializes session state variables."""
    st.set_page_config(page_title=f"{config.COMPANY_NAME} AI", layout="centered", page_icon="🏠")
    st.image(config.COMPANY_LOGO_URL, width=700)

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": f"Hello! I'm your AI design assistant from {config.COMPANY_NAME}. How can I help you create marketing materials today? You can ask me to create a design or provide an MLS ID to get started!"}]
    if "gemini_model" not in st.session_state:
        st.session_state.gemini_model = ai_core.get_gemini_model_with_tool(config.GEMINI_API_KEY)
    if "rich_templates_data" not in st.session_state:
        st.session_state.rich_templates_data = api_utils.load_all_template_details(config.BB_API_KEY)
    if "design_context" not in st.session_state:
        st.session_state.design_context = {"template_uid": None, "modifications": []}
    if "staged_file_bytes" not in st.session_state:
        st.session_state.staged_file_bytes = None
    if "file_was_processed" not in st.session_state:
        st.session_state.file_was_processed = False

# --- 2. CORE LOGIC HANDLERS ---
# Helper function to map MLS data to Bannerbear modifications (Unchanged)
def map_mls_to_modifications(mls_data: dict) -> list:
    modifications = []
    for layer_name, json_path in config.MLS_DATA_MAPPING.items():
        if json_path is None: continue
        value = mls_api_utils.get_from_nested_dict(mls_data, json_path)
        if value:
            if any(img_kw in layer_name.lower() for img_kw in ["photo", "image", "logo", "picture"]):
                modifications.append({"name": layer_name, "image_url": str(value)})
            else:
                modifications.append({"name": layer_name, "text": str(value)})
    logger.info(f"Mapped MLS data to {len(modifications)} modifications.")
    return modifications

# handle_ai_decision function (Unchanged from previous version)
def handle_ai_decision(decision: dict) -> str:
    action = decision.get("action")
    response_text = decision.get("response_text", "I'm not sure how to proceed.")
    trigger_generation = False

    if action == "FETCH_MLS_DATA":
        mls_id = decision.get("mls_listing_id")
        template_uid = decision.get("template_uid")
        if not mls_id or not template_uid:
            return "I need both an MLS ID and a design type (like 'just sold') to get started. Can you provide both?"
        
        with st.spinner(f"Looking up MLS ID {mls_id}..."):
            listing_data = mls_api_utils.fetch_listing_by_mls_id(mls_id)

        if listing_data:
            st.session_state.design_context["template_uid"] = template_uid
            st.session_state.design_context["modifications"] = map_mls_to_modifications(listing_data)
            address = listing_data.get('formatted_address', 'that address')
            return f"Success! I found the listing for **{address}** and pre-filled the available information. You can review and edit the details, or just ask me to make changes. What's next?"
        else:
            return f"I'm sorry, I couldn't find any information for MLS ID `{mls_id}`. Please double-check the ID and try again."

    elif action == "MODIFY":
        new_template_uid = decision.get("template_uid")
        if new_template_uid and new_template_uid != st.session_state.design_context.get("template_uid"):
            if st.session_state.design_context.get("template_uid"):
                trigger_generation = True
            st.session_state.design_context["template_uid"] = new_template_uid
        
        current_mods = {mod['name']: mod for mod in st.session_state.design_context.get('modifications', [])}
        for new_mod in decision.get("modifications", []):
            current_mods[new_mod['name']] = dict(new_mod)
        st.session_state.design_context["modifications"] = list(current_mods.values())

    elif action == "GENERATE":
        trigger_generation = True

    elif action == "RESET":
        st.session_state.design_context = {"template_uid": None, "modifications": []}
        return response_text

    if trigger_generation:
        context = st.session_state.design_context
        if not context.get("template_uid"):
            return "I can't generate an image yet. Please describe the design you want so I can pick a template."

        with st.spinner("Creating your design..."):
            initial_response = api_utils.create_image_async(config.BB_API_KEY, context['template_uid'], context['modifications'])
            if not initial_response:
                return "❌ **Error:** I couldn't start the image generation process."

            final_image = api_utils.poll_for_image_completion(config.BB_API_KEY, initial_response)
            if final_image and final_image.get("image_url_png"):
                response_text += f"\n\n![Generated Image]({final_image['image_url_png']})"
            else:
                response_text = "❌ **Error:** The image generation timed out or failed. Please try again."

    return response_text

# process_user_input function (Unchanged from previous version)
def process_user_input(prompt: str) -> str:
    final_prompt_for_ai = prompt
    if st.session_state.staged_file_bytes:
        with st.spinner("Uploading your image..."):
            image_url = api_utils.upload_image_to_public_url(config.FREEIMAGE_API_KEY, st.session_state.staged_file_bytes)
            st.session_state.staged_file_bytes = None
            if image_url:
                final_prompt_for_ai = f"Image context: The user has uploaded an image, its URL is {image_url}. Their text command is: '{prompt}'"
                st.session_state.file_was_processed = True
            else:
                return "Sorry, there was an error uploading your image. Please try again."

    with st.spinner("Thinking..."):
        ai_response = ai_core.get_ai_decision(
            st.session_state.gemini_model, st.session_state.messages, final_prompt_for_ai,
            st.session_state.rich_templates_data, st.session_state.design_context
        )

    try:
        if ai_response and ai_response.candidates and ai_response.candidates[0].content.parts[0].function_call:
            decision = dict(ai_response.candidates[0].content.parts[0].function_call.args)
            logger.info(f"AI decision: {decision}")
            return handle_ai_decision(decision)
        else:
            logger.error(f"AI did not return a valid function call. Response: {ai_response}")
            return "I'm not sure how to respond to that. Can you clarify what design action you want to take?"
    except (AttributeError, IndexError, TypeError) as e:
        logger.error(f"Error parsing AI response: {e}\nFull Response: {ai_response}")
        return "I'm sorry, I had a problem. Could you please rephrase your request?"


# --- 3. MAIN APPLICATION FLOW ---
initialize_app()

if not all([st.session_state.gemini_model, st.session_state.rich_templates_data, config.BB_API_KEY, config.FREEIMAGE_API_KEY]):
    st.error("Application cannot start. Check API keys and restart.", icon="🛑")
    st.stop()

# --- Display existing chat messages ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# --- REVIEW/EDIT EXPANDER (KeyError FIX) ---
if st.session_state.design_context.get("template_uid"):
    with st.expander("📝 Review and Edit Current Design Details", expanded=False): # Changed to expanded=False for cleaner UI
        mods_dict = {mod['name']: mod for mod in st.session_state.design_context['modifications']}
        template_data = next((t for t in st.session_state.rich_templates_data if t['uid'] == st.session_state.design_context['template_uid']), None)
        
        if template_data:
            # FIX: Use .get('type') to safely access the key, preventing the KeyError
            image_layers = [layer for layer in template_data.get('available_modifications', []) if layer.get('type') == 'image']
            text_layers = [layer for layer in template_data.get('available_modifications', []) if layer.get('type') == 'text']
            
            if image_layers:
                st.subheader("Images")
                for layer in image_layers:
                    current_val = mods_dict.get(layer['name'], {}).get('image_url')
                    if current_val:
                        st.image(current_val, caption=f"{layer['name']} (current)")
                    else:
                        st.info(f"The '{layer['name']}' is not yet set. You can ask me to add it or upload an image.", icon="🖼️")

            if text_layers:
                st.subheader("Text Details")
                for layer in text_layers:
                    current_val = mods_dict.get(layer['name'], {}).get('text', '')
                    st.text_input(label=layer['name'].replace("_", " ").title(), value=current_val, disabled=True)
                st.caption("To change these details, just tell me in the chat! For example: 'Change the price to $500,000'.")


# --- FILE UPLOADER & CHAT INPUT (UI Bug FIX) ---
# This section is now streamlined to prevent the duplicate message bug.

uploaded_file = st.file_uploader("Attach an image (e.g., a listing photo or headshot)", type=["png", "jpg", "jpeg"])
if uploaded_file:
    # We now immediately process the file bytes instead of waiting for a prompt
    st.session_state.staged_file_bytes = uploaded_file.getvalue()
    st.success("✅ Image attached! It will be included with your next message.")
    # Set a flag to show that an image is ready to be sent
    st.session_state.file_was_processed = False 

if prompt := st.chat_input("e.g., 'Create a 'Just Sold' post for MLS 12400539'"):
    # 1. Append and display the user's message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Process the input and get the assistant's response
    response_content = process_user_input(prompt)
    
    # 3. Append and display the assistant's message
    st.session_state.messages.append({"role": "assistant", "content": response_content})
    with st.chat_message("assistant"):
        st.markdown(response_content, unsafe_allow_html=True)

    # 4. Clear the staged file if it was used in this turn
    if st.session_state.file_was_processed:
        st.session_state.staged_file_bytes = None
        st.session_state.file_was_processed = False
        st.rerun() # Rerun to clear the "Image attached" success message