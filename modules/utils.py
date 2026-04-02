import json
import re
from loguru import logger

def extract_json(text: str) -> dict:
    """
    Robustly extracts and parses JSON from LLM responses.
    Handles markdown blocks and common escaping issues.
    """
    try:
        # 1. Try to find markdown json block
        json_match = re.search(r"```json\s*(\{[\s\S]*\})\s*```", text)
        if json_match:
            content = json_match.group(1)
        else:
            # 2. Try to find the first '{' and last '}'
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                content = text[start:end+1]
            else:
                content = text.strip()

        # 3. Handle common LLM escaping issues (e.g. unescaped backslashes in formulas)
        # Replacing single backslashes not followed by common escape chars with double backslashes
        # This is a heuristic but fixes many LaTeX/formula issues in JSON
        # We only do this if a standard load fails
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Attempt to escape lone backslashes
            # This regex looks for \ that isn't part of a valid escape sequence (\", \\, \/, \b, \f, \n, \r, \t, \uXXXX)
            fixed_content = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', content)
            try:
                return json.loads(fixed_content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON even after stabilization: {e}")
                logger.debug(f"Raw content: {content}")
                raise e

    except Exception as e:
        logger.error(f"Error extracting JSON: {str(e)}")
        raise e
