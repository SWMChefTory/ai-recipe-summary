### Task

Summarize the provided comments into a JSON briefing with 2-4 useful sentences (Tips, Substitutions, Warnings, Taste).

### Constraints

1. **Language:** Korean only.
2. **Tone:** Soft & friendly
3. **Length:** 10-50 characters per sentence.
4. **Format:** Use tool `emit_briefing`

### Examples

Input: {"items": ["설탕 대신 꿀...", "양파 오래 볶으니...", "캐러멜라이징 성공"]}
Output: {"items": ["양파를 오래 볶는 것이 성공 비결이라고 해요.", "설탕 대신 꿀을 쓰면 더 깊은 맛이 난대요."]}

Input: {"items": ["물이 빨리 졸아요", "물 더 넣어야함"]}
Output: {"items": ["물이 빨리 졸아들 수 있으니 주의해야 한다고 해요.", "물을 넉넉히 넣는 것을 추천해요."]}

### Input

{{ comments_json }}
