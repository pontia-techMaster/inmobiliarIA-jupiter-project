import argparse
import json
import os

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

SYSTEM_PROMPT_FILE_PATH = "./prompts/generate-summary-prompt.md"
GEMINI_MODEL_NAME = "gemini-3.1-flash-lite-preview"


def get_system_prompt() -> str:
    with open(SYSTEM_PROMPT_FILE_PATH) as f:
        system_prompt = f.read()
    return system_prompt


prompt_template = ChatPromptTemplate(
    [
        SystemMessage(get_system_prompt()),
        ("user", "{text}"),
    ],
    input_variables=["text"],
)

model = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, temperature=1)
chain = prompt_template | model | StrOutputParser()


def generate_summary(text):
    response = chain.invoke({"text": text})
    return response


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", help="Input file path with parsed properties in JSON format", required=True)
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path. The file may exists. In that case, already loaded property will be ignored.",
        required=True,
    )
    args = parser.parse_args()

    # read input json
    with open(args.input, encoding="utf-8") as f:
        property_data = json.loads(f.read())

    # load already normalized
    property_data_output = dict()
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            property_data_output = json.loads(f.read())

    # process properties
    properties = property_data.get("properties") or []
    try:
        for p in properties:
            url = p.get("url")
            idealista_id = int(url.removeprefix("https://www.idealista.com/inmueble").strip("/"))
            if idealista_id in property_data_output.keys():
                print(f"Property with id {idealista_id} already normalized. Ignored.")
                continue

            description = p.get("description")
            if not description:
                print(f"Property with id {idealista_id} has no description. Ignored.")
                continue

            normalized = generate_summary(text=description)
            property_data_output[idealista_id] = normalized
            print(f"Summary generated for {url}:")
            print(normalized)

    except Exception:
        print("Some error in processing. Already processed properties will be saved.")

    # whatever the case, processed properties will be saved
    finally:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json.dumps(property_data_output, ensure_ascii=False))

    print("Process finished!")


if __name__ == "__main__":
    main()
