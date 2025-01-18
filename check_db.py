#!/usr/bin/env python3

from libPodSemSearch import get_db_connection
from tabulate import tabulate
import sys
from dotenv import load_dotenv
import os
# Load environment variables
load_dotenv('.env')
print(os.environ.get('POSTGRES_PASSWORD'))

def get_table_schema():
    """Fetch and display the schema of the episodes table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query to get column information
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length, 
                   is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'episodes'
            ORDER BY ordinal_position;
        """)
        schema = cursor.fetchall()
        
        # Print schema in a nice table format
        headers = ['Column Name', 'Data Type', 'Max Length', 'Nullable', 'Default']
        print("\nTable Schema:")
        print(tabulate(schema, headers=headers, tablefmt='grid'))
        
    except Exception as e:
        print(f"Error fetching schema: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

def check_database():
    """Fetch and display the first few records from the episodes table."""
    try:
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get count of total records
        cursor.execute("SELECT COUNT(*) FROM episodes")
        total_count = cursor.fetchone()[0]
        print(f"\nTotal number of episodes in database: {total_count}\n")
        
        # Fetch first 5 records
        cursor.execute("""
            SELECT id, title, date, number, url, filename, description 
            FROM episodes 
            ORDER BY number 
            LIMIT 5
        """)
        records = cursor.fetchall()
        
        # Print records in a nice table format
        headers = ['ID', 'Title', 'Date', 'Number', 'url', 'Filename']
        print("First 5 episodes:")
        print(tabulate(records, headers=headers, tablefmt='grid'))
        
    except Exception as e:
        print(f"Error accessing database: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv('../.env')
    print("\n=== Database Schema Information ===")
    get_table_schema()
    print("\n=== Database Content Sample ===")
    check_database() 