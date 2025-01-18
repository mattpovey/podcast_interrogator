#!/usr/bin/env python3

import os
import re
from libPodSemSearch import get_db_connection
from config import tscript_dir

def rename_files():
    """
    Rename transcript files to remove episode numbers and update database records.
    New format: YYYYMMDD_TITLE.srt (removing the _NNNN_ part)
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # Get all files in the transcript directory
        for filename in os.listdir(tscript_dir):
            if not filename.endswith('.srt'):
                continue
                
            # Match the current filename pattern
            match = re.search(r"^(\d{8})_\d{4}_(.*)\.srt$", filename)
            if not match:
                print(f"Skipping {filename} - doesn't match expected pattern")
                continue
            
            # Extract components
            date = match.group(1)
            title = match.group(2)
            
            # Create new filename
            new_filename = f"{date}_{title}.srt"
            old_path = os.path.join(tscript_dir, filename)
            new_path = os.path.join(tscript_dir, new_filename)
            
            # Check if new filename already exists
            if os.path.exists(new_path):
                print(f"Warning: {new_filename} already exists, skipping {filename}")
                continue
            
            # Rename the file
            print(f"Renaming {filename} to {new_filename}")
            os.rename(old_path, new_path)
            
            # Update database record
            cursor.execute("""
                UPDATE episodes 
                SET filename = %s 
                WHERE filename = %s
                RETURNING title
            """, (new_filename, filename))
            
            result = cursor.fetchone()
            if result:
                print(f"Updated database record for episode: {result[0]}")
            else:
                print(f"Warning: No database record found for {filename}")
        
        # Commit the changes
        connection.commit()
        print("\nFile renaming and database updates completed successfully")
        
    except Exception as e:
        connection.rollback()
        print(f"Error occurred: {e}")
        raise
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    print("Starting file renaming process...")
    rename_files() 