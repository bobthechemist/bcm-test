import os
import json
import pypdf
import ollama
import argparse

# --- CONFIGURATION ---
ARCHIVE_DIR = 'archive'
DATA_FILE = 'data.json'
MODEL = 'llama3.1:latest'

def parse_args():
    parser = argparse.ArgumentParser(description="BCM Archive AI Summarizer")
    parser.add_name = "BCM Summarizer"
    
    parser.add_argument('-f', '--force', action='store_true', 
                        help='Force AI to re-summarize files that already have summaries.')
    
    parser.add_argument('-p', '--prune', action='store_true', 
                        help='Remove records from data.json if the PDF file no longer exists in the archive.')
    
    return parser.parse_args()

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        reader = pypdf.PdfReader(pdf_path)
        pages = len(reader.pages)
        num_pages = min(pages, 5)
        for i in range(num_pages):
            page_text = reader.pages[i].extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"    [ERROR] Could not read PDF {pdf_path}: {e}")
        return ""

def get_ai_summary(text):
    if not text:
        return "Scanned document/Image (No text layer found).", "Scanned, Image"

    print(f"    [AI] Sending text to {MODEL}...")
    
    prompt = f"""
    You are a professional museum archivist. Summarize the following historical document text.
    Focus on key names, dates, and the general subject matter. 
    
    Provide the output in this EXACT format:
    SUMMARY: [A 2-3 sentence summary]
    KEYWORDS: [Comma separated list of 5 key terms]

    TEXT:
    {text[:4000]} 
    """
    
    try:
        response = ollama.generate(model=MODEL, prompt=prompt)
        response_text = response['response']
        
        summary = "No summary generated."
        keywords = ""
        
        if "SUMMARY:" in response_text:
            summary = response_text.split("SUMMARY:")[1].split("KEYWORDS:")[0].strip()
        if "KEYWORDS:" in response_text:
            keywords = response_text.split("KEYWORDS:")[1].strip()
            
        return summary, keywords
    except Exception as e:
        return f"Ollama Error: {e}", ""

def main():
    args = parse_args()
    print("--- BCM ARCHIVE AI TOOL ---")
    
    # 1. Load Data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
    else:
        data = {"documents": []}

    # 2. Check Archive Folder
    if not os.path.exists(ARCHIVE_DIR):
        print(f"[FATAL] Folder '{ARCHIVE_DIR}' not found.")
        return

    pdf_files_on_disk = [f for f in os.listdir(ARCHIVE_DIR) if f.lower().endswith('.pdf')]

    # 3. Handle Pruning
    if args.prune:
        original_count = len(data['documents'])
        data['documents'] = [doc for doc in data['documents'] if doc['file'] in pdf_files_on_disk]
        pruned_count = original_count - len(data['documents'])
        if pruned_count > 0:
            print(f"[*] PRUNE: Removed {pruned_count} records from JSON because files were missing.")
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        else:
            print("[*] PRUNE: No missing files found. JSON is clean.")

    # 4. Process Summaries
    existing_files = {doc['file']: doc for doc in data['documents']}
    
    print(f"[*] Total PDFs on disk: {len(pdf_files_on_disk)}")
    print(f"[*] Force Mode: {'ON' if args.force else 'OFF'}")

    for index, filename in enumerate(pdf_files_on_disk, 1):
        # Determine if we should skip
        already_has_summary = filename in existing_files and existing_files[filename].get('summary')
        
        if already_has_summary and not args.force:
            continue

        print(f"\n[{index}/{len(pdf_files_on_disk)}] Processing: {filename}")
        file_path = os.path.join(ARCHIVE_DIR, filename)
        content = extract_text_from_pdf(file_path)
        
        summary, keywords = get_ai_summary(content)
        
        if filename in existing_files:
            existing_files[filename]['summary'] = summary
            existing_files[filename]['keywords'] = keywords
        else:
            new_doc = {
                "title": filename.replace(".pdf", ""),
                "cat": "Uncategorized",
                "file": filename,
                "summary": summary,
                "keywords": keywords
            }
            data['documents'].append(new_doc)
        
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"    [DONE] Saved.")

    print("\n--- PROCESS COMPLETE ---")

if __name__ == "__main__":
    main()