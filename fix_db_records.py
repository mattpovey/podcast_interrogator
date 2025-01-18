#!/usr/bin/env python3

import os
import re
from libPodSemSearch import get_db_connection
from config import tscript_dir

def normalize_title(title):
    """Normalize a title for comparison by removing special characters and spaces."""
    return re.sub(r'[^a-zA-Z0-9]', '', title.lower())

def get_date_and_title(filename):
    """Extract date and title from filename, handling both old and new formats."""
    # Try old format first (YYYYMMDD_NNNN_TITLE.srt)
    match = re.search(r"^(\d{8})_\d{4}_(.*)\.srt$", filename)
    if match:
        return match.groups()
    
    # Try new format (YYYYMMDD_TITLE.srt)
    match = re.search(r"^(\d{8})_(.*)\.srt$", filename)
    if match:
        return match.groups()
    
    return None, None

def fix_db_records():
    """
    Diagnose and fix mismatches between database records and transcript files.
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # Get all records from database
        cursor.execute("SELECT id, title, filename FROM episodes")
        db_records = cursor.fetchall()
        
        print(f"\nChecking database records for episode numbers in filenames...")
        updates_needed = []
        
        for record_id, title, old_filename in db_records:
            # Check if this is an old-style filename with episode number
            match = re.search(r"^(\d{8})_\d{4}_(.*)\.srt$", old_filename)
            if match:
                date, title_part = match.groups()
                new_filename = f"{date}_{title_part}.srt"
                
                # Check if the new filename exists on disk
                if os.path.exists(os.path.join(tscript_dir, new_filename)):
                    updates_needed.append({
                        'id': record_id,
                        'old_filename': old_filename,
                        'new_filename': new_filename,
                        'title': title
                    })
        
        if updates_needed:
            print(f"\nFound {len(updates_needed)} records to update:")
            for update in updates_needed:
                print(f"\nRecord ID: {update['id']}")
                print(f"Title: {update['title']}")
                print(f"Old filename: {update['old_filename']}")
                print(f"New filename: {update['new_filename']}")
            
            confirm = input("\nDo you want to update these records? (yes/no): ")
            if confirm.lower() == 'yes':
                print("\nUpdating records...")
                for update in updates_needed:
                    cursor.execute("""
                        UPDATE episodes 
                        SET filename = %s 
                        WHERE id = %s
                    """, (update['new_filename'], update['id']))
                    print(f"Updated: {update['title']}")
                
                connection.commit()
                print("\nAll updates completed successfully.")
            else:
                print("\nUpdate cancelled.")
        else:
            print("\nNo filename updates needed.")
        
        # Verify the results
        cursor.execute("SELECT filename FROM episodes")
        db_filenames = {row[0] for row in cursor.fetchall()}
        transcript_files = {f for f in os.listdir(tscript_dir) if f.endswith('.srt')}
        
        missing_in_db = transcript_files - db_filenames
        missing_on_disk = db_filenames - transcript_files
        
        if missing_in_db or missing_on_disk:
            print("\nRemaining issues after updates:")
            if missing_in_db:
                print(f"\nFiles on disk without database records ({len(missing_in_db)}):")
                for filename in sorted(missing_in_db):
                    print(f"  {filename}")
                    # Try to find a matching record
                    date, title = get_date_and_title(filename)
                    if date and title:
                        cursor.execute("""
                            SELECT filename 
                            FROM episodes 
                            WHERE filename LIKE %s
                        """, (f"{date}_%{title}",))
                        matches = cursor.fetchall()
                        if matches:
                            print(f"    Possible match in database: {matches[0][0]}")
            
            if missing_on_disk:
                print(f"\nDatabase records without files ({len(missing_on_disk)}):")
                for filename in sorted(missing_on_disk):
                    print(f"  {filename}")
        else:
            print("\nAll files and database records now match correctly!")
        
    except Exception as e:
        connection.rollback()
        print(f"Error occurred: {e}")
        raise
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    print("Starting database record fix process...")
    fix_db_records() 