import json
import logging
import google.generativeai as genai
from src.config import GEMINI_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligenceAgent:
    def __init__(self):
        """
        Initializes the IntelligenceAgent with the Gemini API key.
        """
        if not GEMINI_API_KEY:
            logger.warning(
                "GEMINI_API_KEY is not set. Intelligence features will not work."
            )
            self.model = None
            return

        genai.configure(api_key=GEMINI_API_KEY)

        # Determine model to use
        # Instructions say: Use `genai.GenerativeModel('gemini-1.5-pro')` or `gemini-1.5-flash`
        # if `gemini-1.5-pro` is not available, but user requested `gemini-1.5-pro`.
        # I will try to use pro, and if it fails during generation (which is hard to predict at init),
        # I might need a fallback mechanism. However, usually model selection happens at instantiation.
        # For simplicity and robustness, I'll default to 'gemini-1.5-pro' as primary and 'gemini-1.5-flash' as fallback
        # if the specific error indicates model unavailability, but the library doesn't easily expose availability checks.
        # So I will just initialize with 'gemini-1.5-pro' and catch errors in analyze_article to try flash if needed
        # or just stick to one. The prompt says "if gemini-1.5-pro is not available", which might mean connection error or 404.

        self.model_name = "gemini-1.5-pro"
        self.fallback_model_name = "gemini-1.5-flash"
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as e:
            logger.error(f"Failed to initialize model {self.model_name}: {e}")
            self.model = None

    def analyze_article(self, article):
        """
        Analyzes an article using Gemini to extract summary, author, entities, and relevance score.

        Args:
            article (dict): The article dictionary containing 'title' and 'content' or 'description'.

        Returns:
            dict: JSON object with summary, author, entities, and relevance_score.
                  Returns None if analysis fails.
        """
        if not self.model:
            logger.error("Model not initialized.")
            return None

        title = article.get("title", "No Title")
        content = article.get("content") or article.get("description") or "No Content"

        prompt = f"""
        Analyze the following news article and provide a JSON output.
        
        Article Title: {title}
        Article Content: {content}

        Output JSON format:
        {{
            "summary": "3 sentences summary of the article",
            "author": "Name of the author if available, else 'Unknown'",
            "entities": ["List of key companies or organizations mentioned, with a brief connection bio in parentheses, e.g., 'Google (Tech Giant)'"],
            "relevance_score": <integer between 1 and 10 indicating relevance to tech/AI/business news>
        }}
        
        Ensure the output is valid JSON. Do not include markdown formatting like ```json ... ```.
        """

        try:
            response = self._generate_content(prompt)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Error analyzing article with {self.model_name}: {e}")
            # Fallback logic could go here if needed, but for now just logging.
            # If the user specifically wanted fallback logic upon failure:
            if self.fallback_model_name:
                logger.info(f"Retrying with fallback model: {self.fallback_model_name}")
                try:
                    fallback_model = genai.GenerativeModel(self.fallback_model_name)
                    response = fallback_model.generate_content(prompt)
                    return self._parse_response(response)
                except Exception as fallback_e:
                    logger.error(
                        f"Error analyzing article with fallback {self.fallback_model_name}: {fallback_e}"
                    )

            return None

    def _generate_content(self, prompt):
        """Helper to generate content to allow for easier mocking or swapping."""
        return self.model.generate_content(prompt)

    def _parse_response(self, response):
        """Parses the Gemini response text into a JSON object."""
        try:
            text = response.text
            # Clean up markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}. Response text: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None
