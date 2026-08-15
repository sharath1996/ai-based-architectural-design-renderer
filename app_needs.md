## AI Photo Studio — Product Needs (MVP)

Purpose
-------
Design an AI Photo Studio focused on a simple, reliable two-step workflow:

- Step A — Scene Description: user supplies one base image + zero-or-more reference images and short prompts; an LLM synthesizes a single, detailed scene description tailored to the selected photography style.
- Step B — Image Generation: after the user reviews/edits/approves the scene description, the backend generates exactly one final image using the approved description plus all image inputs and style prompts.
- Step C - Image Editing: After the initial image is generated, edit the images on based on the user's need (This feature is not needed for now)



Principles
----------
- Single canonical flow for all styles (style packs change text prompts to the LLM and generation model, not code flow).

- The LLM's role is to create a human- and AI-readable scene description that the image generator consumes.

- The user always reviews and approves the scene description before generation.

Prompt Pack Requirements
-----------------------
Each style folder must include:

- `prompt.txt` — must be injected into the LLM call to enforce style constraints.

End-to-end User Flow (fresh)
----------------------------

1. User chooses a style pack from the dropdown.
2. User uploads exactly one base (anchor) image and zero-or-more reference images.
3. Optionally, the user enters a short per-reference intent for each support image and a short global user prompt.
4. User clicks `Describe Scene`.
   - Backend: collects images, per-image intents, global prompt and injects `prompt.txt` for the chosen style into an LLM call.
   - LLM returns the scene description. 

5. UI: displays editable `scene_description`
6. User edits and approves the scene description.
7. Backend updates the scene description.
7. User clicks `Generate`.
   - Backend assembles the complete collection and asks the LLM to generate the full images. 
8. Backend returns a single base64 image.
9. UI displays the image and offers download/save-as-reference.

API Endpoints (recommended)
---------------------------

1. Post method for selecting the style pack
2. Post method to upload the Base or Primary image along with the brief description
3. Post method to upload the reference image along with the brief description
4. Get method to get the scene description
5. Post method to update the scene description
6. Get method to generate the final image. 4

(Future)
7. Post method to suggest the corrections
8. Get method to get the corrected image. 

