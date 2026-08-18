# Demonstration Guide

Use the studio as a live, reviewable creative workflow, not as a one-click black box. The strongest demonstration makes the input, the intent, the editable scene description, and the final output visible.

## Jewellery on model

1. Select **Jewellery photography**.
2. Upload a product or model image as the base. Good starting points include `ref_01/arnav/base.jpg`, `ref_01/Lavanya/base_ref.png`, `ref_01/She/base_ref.png`, or `ref_01/taruni_jewel/base_product.png`.
3. Add one or two references from the same set. State their purpose, such as: `Use this for warm editorial lighting and a premium sari styling direction; do not alter the jewellery design.`
4. In the global prompt, request the final treatment: `Create a clean, premium catalogue portrait with natural skin texture and jewellery as the hero subject.`
5. Generate the scene description, point out the preservation requirements, make any correction, approve it, and generate.

Talk track: the base image protects product identity; references communicate the desired finish; the editable description makes the creative decision inspectable before generation.

## Jewellery product staging

1. Select **Jewellery photography**.
2. Upload `ref_01/rat/product.png` or `ref_01/mansi/base_ref].jpg` as the base.
3. Add `ref_01/mansi/box_pos.png` and `ref_01/mansi/props.png` as references with the intent: `Use the box placement and prop mood only. Keep the base jewellery unchanged.`
4. Request a clean commercial product image with realistic metal, gemstones, and controlled shadows.

Talk track: the same process can turn raw product evidence into a more deliberate retail composition without asking the user to write a production-grade prompt from scratch.

## Kitchen visualization

1. Select **Architectural photography**.
2. Upload `ref_01/kitchen/basic_kitchen.png` as the base image.
3. Add `cabinets style.png`, `stove-01.png`, `ref_01.png`, and `ref_02.png` with precise intents for materials or fixtures.
4. Request a polished interior visualization while retaining the original walls, window positions, cabinetry placement, and camera view.

Talk track: visual direction can change, but the spatial plan remains the constraint.

## Presenting results

Show the original base image beside the final output. Explain which image was the anchor and which images were references. Keep examples and generated outputs from `ref_01` available as proof of the types of transformation the workflow is designed to support.