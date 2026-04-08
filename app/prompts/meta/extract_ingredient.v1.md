Extract all cooking ingredients from the video description and comments of the channel owner below.

Return ONLY a JSON object with this exact structure:
[
  {"name": "string", "amount": number, "unit": "string"}
]

Rules:
1. **Translation (STRICT):**
  - Translate all ingredient names and units into **{{ language }}**.

2. **Missing Values:**
  - If amount is missing, set it to 0.
  - If unit is missing, set it to "" (empty string).

3. **Handling Dual Units (CRITICAL):**
  - If an ingredient has dual measurements (e.g., "1 cup (200g)"), extract ONLY the primary measurement.
  - Example: "통마늘 8알(50g)" -> {"name": "Garlic", "amount": 8, "unit": "cloves"}. Ignore "50g".

4. **Duplicate Content:**
  - Deduplicate ingredients found in both description and comments.

5. **Structured Ingredient List Requirement:**
  - Extract ONLY from explicitly labeled sections (e.g., "재료", "Ingredients", "Checklist ☑️").
  - Ignore ingredients mentioned only in the conversational story or introduction.

Description:
{{ description }}

Comments of the channel owner:
{{ channel_owner_top_level_comments }}

Target Language:
{{ language }}