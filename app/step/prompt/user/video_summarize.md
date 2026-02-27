Respond only via the `emit_recipe_steps` function. Do not output plain text.

[Target Language]
- {{ language }} (no mixed languages)

[Goal]
- Organize the core cooking actions from the recipe video into `steps` so the cooking flow can be reproduced.

[Use of Information Sources]
- Use visuals (actions/state changes) + subtitles (ingredients/quantities) + audio (order/heat/time/conditions) together.
- If quantities or ingredient names conflict: subtitles > audio. Do not infer quantities/ingredients from visuals alone (omit if uncertain).

[Include (Core)]
- Actions that change ingredient state: slice/chop/add/pour/mix/toss/stir-fry/boil/reduce/bake/fry/blanch/plate/sprinkle, etc.
- When possible, include follow-up actions that produce outcomes after "add/pour" (e.g., mix/stir-fry/toss).
- If time/heat/state criteria appear in audio/subtitles, reflect them in the action text.

[Subtitle Rules (Important)]
- Each `step.subtitle` should summarize the step's purpose/work unit as a short, concise phrase.
- Split steps when the cooking objective or ingredient state changes (do not over-merge).
- Avoid broad subtitles that span multiple phases; prefer one clear objective per step.

[Exclude (Noise)]
- Exclude greetings, promotions, channel talk, or meta commentary unrelated to cooking actions.
- Exclude taste reviews/impressions unless they are used as cooking judgment criteria (doneness/viscosity/color change).

[Expression Rules]
- (When language is Korean) `descriptions[].text` should use a nominal ending (`~기`/`~함`) and specific objects where possible.
- Keep each `descriptions[].text` within 90 characters when possible.
- Sort groups in ascending time order.
- Prefer setting `step.start` to the first `description.start` in the same group.

[Timecode Rules (Important)]
- `start` must be output as a **string in `hh:mm:ss` format** only.
- Do not output numeric-only values (e.g., `1130`, `583`) and do not output decimals.
- `mm:ss` is not allowed. Always use zero-padded `hh:mm:ss`.
- Convert subtitle/audio time references to `hh:mm:ss` before output.
  - Example: `9 min 43 sec -> 00:09:43`
  - Example: `1 h 02 min 03 sec -> 01:02:03`

[Output]
- If there are no cooking actions, return {{"steps": []}}.
