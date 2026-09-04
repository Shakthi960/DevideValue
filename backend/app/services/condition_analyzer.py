import json
import os

from google import genai
from google.genai import types


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MODEL_NAME = "gemini-3.6-flash"


VIEW_INSTRUCTIONS = {
    "front": """
Inspect the FRONT of the smartphone.

Focus on:
- Display glass
- Screen cracks
- Screen scratches
- Dead/broken display areas if visibly apparent
- Front camera area
- Bezels
- Visible front-frame damage

Do not judge the rear panel or side frame unless clearly visible.
""",

    "back": """
Inspect the BACK of the smartphone.

Focus on:
- Rear glass/panel
- Back scratches
- Back cracks
- Dents
- Camera module
- Camera lens damage
- Rear panel condition
- Visible frame damage around the back edges

Do not judge the display because it is not visible from this view.
""",

    "left": """
Inspect the LEFT SIDE of the smartphone.

Focus on:
- Left frame
- Buttons if visible
- Scratches
- Dents
- Bends
- Paint peeling
- Frame cracks
- Edge damage

Do not judge the screen or rear panel unless clearly visible.
""",

    "right": """
Inspect the RIGHT SIDE of the smartphone.

Focus on:
- Right frame
- Power button
- Volume buttons if visible
- Scratches
- Dents
- Bends
- Paint peeling
- Frame cracks
- Edge damage

Do not judge the screen or rear panel unless clearly visible.
""",

    "top": """
Inspect the TOP of the smartphone.

Focus on:
- Top frame
- Microphone openings if visible
- Speaker openings if visible
- Scratches
- Dents
- Cracks
- Paint peeling
- Frame damage

Do not judge the display condition unless clearly visible.
""",

    "bottom": """
Inspect the BOTTOM of the smartphone.

Focus on:
- Charging port
- USB port condition
- Speaker openings
- Microphone openings
- Bottom frame
- Scratches
- Dents
- Cracks
- Port damage
- Paint peeling

Do not judge the display condition unless clearly visible.
""",
}


CONDITION_PROMPT = """
You are a professional smartphone resale-condition inspection AI.

Analyze the provided smartphone photograph carefully.

Only report damage that is visually supported by the image.
Do not invent damage.

The purpose of this analysis is to help estimate the
resale/exchange value of a used smartphone.

Return ONLY valid JSON.

Required structure:

{
  "phone_visible": true,
  "view_quality": "good",
  "screen_condition": "not_visible",
  "body_condition": "good",

  "scratches": {
    "detected": false,
    "severity": "none",
    "description": ""
  },

  "dents": {
    "detected": false,
    "severity": "none",
    "description": ""
  },

  "cracks": {
    "detected": false,
    "severity": "none",
    "description": ""
  },

  "frame_damage": {
    "detected": false,
    "severity": "none",
    "description": ""
  },

  "visible_damage_score": 0,
  "confidence": 0,
  "notes": ""
}

Rules:

1. visible_damage_score must be between 0 and 100.

2. 0 means no visible damage.

3. 100 means extremely severe visible damage.

4. confidence must be between 0 and 1.

5. Severity must be exactly one of:
   "none", "minor", "moderate", "severe".

6. If a particular component is not visible,
   use "not_visible" where appropriate.

7. Do not assume hidden or internal damage.

8. Do not diagnose hardware faults from appearance alone.

9. If the photo is blurry, dark, obstructed,
   or the phone is too small, reduce confidence.

10. Describe only visible physical characteristics.

11. Be conservative. When uncertain, say so
    in the notes instead of inventing damage.

12. The result will be used by another program,
    so JSON must be valid and contain no markdown.
"""


def analyze_condition(
    image_bytes: bytes,
    photo_type: str
):
    """
    Analyze one smartphone inspection photo
    using Gemini Vision.
    """

    photo_type = photo_type.lower().strip()

    view_instruction = VIEW_INSTRUCTIONS.get(
        photo_type,
        "Analyze the visible physical condition of the phone."
    )

    prompt = f"""
PHOTO VIEW:
{photo_type}

VIEW-SPECIFIC INSTRUCTIONS:
{view_instruction}

GENERAL ANALYSIS RULES:
{CONDITION_PROMPT}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            ),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    if not response.text:
        raise ValueError(
            "Gemini returned an empty response."
        )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON."
        ) from exc

    return result