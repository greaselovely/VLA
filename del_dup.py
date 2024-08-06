import os
import hashlib
from datetime import datetime
from pathlib import Path

def compute_hash(file_path):
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_and_remove_duplicate_images(folder_path):
    """Check for duplicate images based on SHA256 hash and remove the second duplicate."""
    # Get all jpg files in the folder
    image_files = sorted(Path(folder_path).glob('vla.*.jpg'))
    
    # Filter and sort files based on the specific naming pattern
    valid_files = []
    for file in image_files:
        try:
            # Parse the date and time from the filename
            datetime.strptime(file.stem, 'vla.%d%m%Y.%H%M%S')
            valid_files.append(file)
        except ValueError:
            # Skip files that don't match the expected format
            continue
    
    valid_files.sort()
    
    removed_files = []
    for i in range(len(valid_files) - 1):
        current_file = valid_files[i]
        next_file = valid_files[i + 1]
        
        current_hash = compute_hash(current_file)
        next_hash = compute_hash(next_file)
        
        if current_hash == next_hash:
            # Remove the second file
            next_file.unlink()
            removed_files.append(next_file)
            print(f"Removed duplicate file: {next_file.name}")
    
    return removed_files

def main():
    folder_path = input("Enter the path to the folder containing the images: ")
    removed_files = check_and_remove_duplicate_images(folder_path)
    
    if removed_files:
        print(f"\nRemoved {len(removed_files)} duplicate images:")
        for file in removed_files:
            print(f"- {file.name}")
    else:
        print("No duplicate images found.")

if __name__ == "__main__":
    main()