"""
Test script for Supabase connector.

This script demonstrates CRUD operations on the Test table.
Table schema: id (primary key), created_at (timestamp), content (text)
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from supabase_connector import SupabaseConnector


def main():
    """Run CRUD operations test on the Test table."""
    # Load environment variables
    load_dotenv()

    # Initialize connector
    print("=" * 60)
    print("Initializing Supabase Connector...")
    print("=" * 60)
    connector = SupabaseConnector()
    print(f"Connected to: {connector.url}")
    print()

    table_name = "Test"

    # 1. CREATE - Insert new records
    print("=" * 60)
    print("1. CREATE - Inserting new records")
    print("=" * 60)

    test_data = [
        {"content": f"Test message 1 - {datetime.now().isoformat()}"},
        {"content": f"Test message 2 - {datetime.now().isoformat()}"},
        {"content": f"Test message 3 - {datetime.now().isoformat()}"}
    ]

    inserted = connector.insert(table_name, test_data)
    print(f"Inserted {len(inserted)} records:")
    for record in inserted:
        print(f"  - ID: {record['id']}, Content: {record['content']}")
    print()

    # Save IDs for later operations
    inserted_ids = [record['id'] for record in inserted]

    # 2. READ - Select all records
    print("=" * 60)
    print("2. READ - Selecting all records")
    print("=" * 60)

    all_records = connector.select(table_name, order_by="created_at", ascending=False)
    print(f"Total records in table: {len(all_records)}")
    for record in all_records[:5]:  # Show first 5
        print(f"  - ID: {record['id']}, Created: {record['created_at']}, Content: {record['content'][:50]}")
    if len(all_records) > 5:
        print(f"  ... and {len(all_records) - 5} more records")
    print()

    # 3. READ - Select specific record
    print("=" * 60)
    print("3. READ - Selecting specific record by ID")
    print("=" * 60)

    specific_record = connector.select(table_name, filters={"id": inserted_ids[0]})
    if specific_record:
        record = specific_record[0]
        print(f"Found record:")
        print(f"  - ID: {record['id']}")
        print(f"  - Created: {record['created_at']}")
        print(f"  - Content: {record['content']}")
    print()

    # 4. UPDATE - Update a record
    print("=" * 60)
    print("4. UPDATE - Updating a record")
    print("=" * 60)

    updated_content = f"Updated content - {datetime.now().isoformat()}"
    updated = connector.update(
        table_name,
        {"content": updated_content},
        {"id": inserted_ids[0]}
    )
    if updated:
        print(f"Updated record ID {inserted_ids[0]}:")
        print(f"  - New content: {updated[0]['content']}")
    print()

    # 5. COUNT - Count records
    print("=" * 60)
    print("5. COUNT - Counting total records")
    print("=" * 60)

    total_count = connector.count(table_name)
    print(f"Total records in table: {total_count}")
    print()

    # 6. DELETE - Delete records
    print("=" * 60)
    print("6. DELETE - Deleting test records")
    print("=" * 60)

    for record_id in inserted_ids:
        deleted = connector.delete(table_name, {"id": record_id})
        if deleted:
            print(f"  - Deleted record ID: {record_id}")
    print()

    # Verify deletion
    print("=" * 60)
    print("7. VERIFY - Checking deletion")
    print("=" * 60)

    final_count = connector.count(table_name)
    print(f"Records deleted: {total_count - final_count}")
    print(f"Remaining records: {final_count}")
    print()

    print("=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
