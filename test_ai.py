
import asyncio
import os

from dotenv import load_dotenv
from google.genai import errors

from app.services.ai_service import WorkUpdateExtractor


async def main():

    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    extractor = WorkUpdateExtractor(
        api_key=api_key,
        model=model
    )

    test_message = (
        "Bu hafta elektrik tesisatının yaklaşık %70'ini "
        "tamamladık. Ancak kablo tedarikinde sorun yaşadığımız "
        "için kalan kısmı bitiremedik. Malzemeler yarın gelirse "
        "cuma gününe kadar bitirmeyi planlıyoruz."
    )

    try:
        print(f"Testing model: {model}")
        print("Analyzing work update...\n")

        result = await extractor.extract(test_message)

        print("SUCCESS!")
        print("\nAI ANALYSIS RESULT")
        print("------------------")
        print(result.model_dump_json(indent=2))

    except errors.APIError as exc:
        print(f"Gemini API Error: HTTP {exc.code}")
        print(exc.message)

    except Exception as exc:
        print(f"Error: {type(exc).__name__}")
        print(str(exc))

    finally:
        await extractor.close()


if __name__ == "__main__":
    asyncio.run(main())