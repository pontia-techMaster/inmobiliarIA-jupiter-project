import argparse
import json

from dotenv import load_dotenv
from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings

load_dotenv()

GEMINI_MODEL_NAME = "gemini-embedding-001"


model = GoogleGenerativeAIEmbeddings(model=GEMINI_MODEL_NAME)


def generate_embeddings(fragments):
    vectors = model.embed_documents(fragments, task_type="retrieval_document", batch_size=10)
    return vectors


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", help="Input file path with normalized descriptions in JSON format", required=True)
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path",
        required=True,
    )
    args = parser.parse_args()

    # read input json
    with open(args.input, encoding="utf-8") as f:
        descriptions = json.loads(f.read())

    # generate embeddings
    ids, descriptions = zip(*descriptions.items(), strict=True)
    print(len(ids), len(descriptions))
    print({_id: v for _id, v in zip(ids, [list() for i in range(len(ids))], strict=True)})
    vectors = generate_embeddings(fragments=list(descriptions))
    print(len(vectors), len(vectors[0]))

    # # dump data
    data = {_id: v for _id, v in zip(ids, vectors, strict=True)}
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False))

    print("Process finished!")


if __name__ == "__main__":
    main()
