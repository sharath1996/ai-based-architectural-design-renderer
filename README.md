# AI Photo Studio

AI Photo Studio turns a product or spatial reference into a polished commercial image while keeping the original subject, layout, and composition under the selected photography style.

The MVP contains a Streamlit studio, a FastAPI backend, and prompt packs for architectural, food, and jewellery photography. The workflow is deliberately reviewable: the AI first produces an editable scene description, then generates one final image from the approved direction.

## What it can demonstrate

- **Jewellery photography:** keep the anchor jewellery and model as the hero while improving lighting, material rendering, cleanliness, and catalog readiness.
- **Architectural photography:** retain the supplied room geometry while applying specified finishes, lighting, atmosphere, and design detail.
- **Food photography:** retain the dish, plating, framing, and core ingredients while refining presentation and commercial polish.

The attached local reference library in [`ref_01`](ref_01) is a presentation asset for these capabilities. It is not loaded automatically by the application. Choose images from it as uploads when running a demonstration:

| Scenario | Suggested anchor | Suggested supporting references | What it demonstrates |
| --- | --- | --- | --- |
| Jewellery on model | `ref_01/arnav/base.jpg`, `ref_01/Lavanya/base_ref.png`, `ref_01/She/base_ref.png`, or `ref_01/taruni_jewel/base_product.png` | Matching `model_ref.png`, `model_output.png`, `box_pos.png`, or completed output images in the same folder | Product fidelity plus premium on-model presentation |
| Jewellery product staging | `ref_01/rat/product.png` or `ref_01/mansi/base_ref].jpg` | `ref_01/mansi/box_pos.png` and `ref_01/mansi/props.png` | Packaging, prop direction, and controlled product composition |
| Kitchen visualization | `ref_01/kitchen/basic_kitchen.png` or a room-view image at the root of `ref_01` | `ref_01/kitchen/cabinets style.png`, `ref_01/kitchen/stove-01.png`, `ref_01/kitchen/ref_01.png`, and `ref_01/kitchen/ref_02.png` | Layout-preserving interior refinement |

For a complete audience-facing walkthrough, see the [local Wiki source](wiki/Home.md). These pages are ready to copy into the repository's GitHub Wiki.

## 1) Install dependencies

From the workspace root:

```powershell
pip install -r .\backend_api\requirements.txt
pip install -r .\frontend_streamlit\requirements.txt
```

## 2) Configure environment

Edit `backend_api/.env` and set:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_PRICE_GPT_4_1_MINI_INPUT_PER_1M=0.40
OPENAI_PRICE_GPT_4_1_MINI_OUTPUT_PER_1M=1.60
OPENAI_PRICE_GPT_4O_2024_08_06_INPUT_PER_1M=2.50
OPENAI_PRICE_GPT_4O_2024_08_06_OUTPUT_PER_1M=10.00
OPENAI_PRICE_GPT_IMAGE_1_TEXT_INPUT_PER_1M=5.00
OPENAI_PRICE_GPT_IMAGE_1_IMAGE_INPUT_PER_1M=10.00
OPENAI_PRICE_GPT_IMAGE_1_TEXT_OUTPUT_PER_1M=0.00
OPENAI_PRICE_GPT_IMAGE_1_IMAGE_OUTPUT_PER_1M=40.00
```

Environment values are loaded from `backend_api/.env` via `python-dotenv`.
If pricing env vars are left blank, the app still logs usage per client, but `estimated_cost_usd` remains empty.
The `gpt-image-1` tracker now supports separate text/image input and output rates, matching the pricing page's multimodal pricing table.

## 3) Run with batch files (recommended)

From the workspace root, run each in a separate terminal:

```powershell
.\run_backend.bat
.\run_frontend.bat
```

- Backend: http://localhost:8000
- Frontend: http://localhost:8501

## 4) Manual run (fallback)

Run from `backend_api`:

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run from `frontend_streamlit`:

```powershell
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

## 5) Use the app

1. Open the Streamlit UI and keep the backend URL as `http://localhost:8000`.
2. Select a photography style in **Studio settings**.
3. Upload one **base image**. This is the visual anchor that the selected prompt pack is designed to preserve.
4. Add optional reference images and state exactly what they should influence, such as lighting, packaging, materials, styling, or cabinetry.
5. Add a global prompt and select **Generate scene description**.
6. Review and edit the scene description, then select **Update scene description**.
7. Select **Generate final image** and download the resulting PNG.

Use generated images in `ref_01` as proof points when presenting the tool, but use the original product or layout image as the base upload. This gives the model a clear fidelity anchor and uses the other images only for visual direction.

## Publish the wiki

The GitHub Wiki source is maintained in [`wiki`](wiki) so it can be reviewed with the application code. To publish it, enable **Wikis** in the repository settings, clone the repository's GitHub Wiki repository (usually `<repository-url>.wiki.git`), copy the contents of `wiki` to that clone's root, then commit and push. GitHub will render `Home.md` as the wiki landing page and `_Sidebar.md` as its navigation.

## Notes

- The base image is required; references are optional.
- The active prompt pack affects both scene direction and final generation.
- Generated images are held in the active session; the app does not automatically ingest `ref_01` or persist uploads as a library.
- Error handling is intentionally simple for the MVP and backend exceptions are surfaced in the UI.
- OpenAI calls remain backend-only.
