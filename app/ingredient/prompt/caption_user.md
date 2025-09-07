Extract all cooking ingredients mentioned in the captions below.

Return ONLY a JSON object with this exact structure:
[
{"name": "string", "amount": number, "unit": "string"}
]

Rules:

- If amount is missing, set it to 0
- If unit is missing, set it to "" (empty string)
- Deduplicate and normalize simple synonyms
- Return ONLY the JSON object, no other text
- Language of captions: {{ lang_code }}

Captions:
{{ captions }}
