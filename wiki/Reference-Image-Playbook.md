# Reference Image Playbook

The quality of the brief depends on assigning each image one clear role.

## Base image: the anchor

Upload exactly one base image. It should contain the subject that must remain recognizable in the final result.

| Style | Anchor to preserve |
| --- | --- |
| Jewellery | Product construction, stone placement, chain links, engraving, model identity, pose, and crop. |
| Architectural | Room geometry, proportions, walls, windows, doors, furniture placement, and camera view. |
| Food | Dish identity, plating, framing, plate placement, and core ingredients. |

Use the clearest available source. Describe the non-negotiable details in the base-image description.

## Reference images: visual direction

Add zero or more references after the base image. Each reference should have a short intent that names what it may influence. Useful intents include:

- `Use this lighting direction only; preserve the base product and camera framing.`
- `Match this cabinetry finish and backsplash material; do not move walls or windows.`
- `Use this packaging and prop mood; do not add text, logos, or watermarks.`
- `Match this color grading and material realism; keep the base jewellery geometry unchanged.`

Avoid vague phrases such as `make it better`. An explicit constraint is more valuable than a long list of style adjectives.

## The global prompt

Use the global prompt to define the desired final outcome across all inputs. Keep it outcome-oriented, for example:

`Create a warm, premium jewellery campaign image with natural skin texture, precise gold reflections, and the necklace as the central focus.`

The scene description is the checkpoint. Review it for accidental changes to the anchor before generating the final image.

## Reference library conventions

The `ref_01` folders are examples for product-photography demonstrations, not an application-managed library. Their names imply useful roles:

- `base`, `base_ref`, and `base_product`: candidate anchor images.
- `model_ref`, `props`, `box_pos`, cabinet, and stove images: candidate direction references.
- `generated_final_output`, `model_output`, and `output_01`: prior result examples for comparison or presentation, not required inputs.