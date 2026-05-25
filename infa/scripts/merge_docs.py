import os

directories = ["design", "docs", "backend/layer5/docs"]
output_file = "AI_KNOWLEDGE_BASE.md"

def get_all_md_files(dirs):
    md_files = []
    for d in dirs:
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith(".md"):
                    md_files.append(os.path.join(root, file))
    return md_files

def merge_files(files, output):
    with open(output, 'w', encoding='utf-8') as outfile:
        outfile.write("# AI KNOWLEDGE BASE\n")
        outfile.write("This file contains the consolidated documentation from the design and docs directories.\n")
        outfile.write("Use this file as the primary source of truth for architectural and design knowledge.\n\n")
        outfile.write("## Table of Contents\n")
        
        for file in files:
            outfile.write(f"- {file}\n")
            
        outfile.write("\n---\n\n")
        
        for file in files:
            outfile.write(f"## File: {file}\n\n")
            try:
                with open(file, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"Error reading file {file}: {e}\n")
            outfile.write("\n\n---\n\n")

if __name__ == "__main__":
    files_to_merge = get_all_md_files(directories)
    files_to_merge.sort()
    merge_files(files_to_merge, output_file)
    print(f"Merged {len(files_to_merge)} files into {output_file}")
