import os

directories = ["backend/layer5/agents/logic/prompts", "backend/layer5/agents/mapping/prompts"]
replacements = {
    "日本語": "{TARGET_LANGUAGE}",
    "Japanese (日本語)": "{TARGET_LANGUAGE}",
    "Japanese comments only": "Comments in {TARGET_LANGUAGE} only",
    "Japanese only": "{TARGET_LANGUAGE} only",
    "All comments in Japanese": "All comments in {TARGET_LANGUAGE}"
}

def update_files():
    count = 0
    for d in directories:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".md"):
                path = os.path.join(d, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                original_content = content
                for old, new in replacements.items():
                    content = content.replace(old, new)
                
                if content != original_content:
                    with open(path, 'w', encoding='utf-8') as file:
                        file.write(content)
                    count += 1
                    print(f"Updated {path}")
    print(f"Total updated: {count}")

if __name__ == "__main__":
    update_files()
