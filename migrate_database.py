#!/usr/bin/env python3
"""
Database Migration Script for User Isolation

This script migrates the existing database to support user isolation by:
1. Adding user_id columns to all tables
2. Assigning a default user_id to existing data
3. Creating indexes for better performance
"""

import sqlite3
import uuid
import os

DATABASE = 'feedback.db'
DEFAULT_USER_ID = 'legacy_user_' + str(uuid.uuid4())[:8]

def migrate_database():
    """Migrate the database to support user isolation."""
    print(f"Starting database migration...")
    print(f"Default user ID for existing data: {DEFAULT_USER_ID}")
    
    if not os.path.exists(DATABASE):
        print(f"Database {DATABASE} not found. Creating new database with user isolation.")
        return
    
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            
            # Check if migration is already done
            cursor.execute("PRAGMA table_info(feedback)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'user_id' in columns:
                print("Migration already completed. Database supports user isolation.")
                return
            
            print("Adding user_id columns to all tables...")
            
            # Add user_id column to feedback table
            try:
                cursor.execute('ALTER TABLE feedback ADD COLUMN user_id TEXT')
                print("✓ Added user_id to feedback table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("✓ user_id already exists in feedback table")
                else:
                    raise
            
            # Add user_id column to wishlist table
            try:
                cursor.execute('ALTER TABLE wishlist ADD COLUMN user_id TEXT')
                print("✓ Added user_id to wishlist table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("✓ user_id already exists in wishlist table")
                else:
                    raise
            
            # Add user_id column to price_alerts table
            try:
                cursor.execute('ALTER TABLE price_alerts ADD COLUMN user_id TEXT')
                print("✓ Added user_id to price_alerts table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("✓ user_id already exists in price_alerts table")
                else:
                    raise
            
            # Add user_id column to search_history table
            try:
                cursor.execute('ALTER TABLE search_history ADD COLUMN user_id TEXT')
                print("✓ Added user_id to search_history table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("✓ user_id already exists in search_history table")
                else:
                    raise
            
            # Add user_id column to price_history table
            try:
                cursor.execute('ALTER TABLE price_history ADD COLUMN user_id TEXT')
                print("✓ Added user_id to price_history table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("✓ user_id already exists in price_history table")
                else:
                    raise
            
            print("\nUpdating existing data with default user_id...")
            
            # Update existing feedback data
            cursor.execute('UPDATE feedback SET user_id = ? WHERE user_id IS NULL', (DEFAULT_USER_ID,))
            feedback_count = cursor.rowcount
            print(f"✓ Updated {feedback_count} feedback records")
            
            # Update existing wishlist data
            cursor.execute('UPDATE wishlist SET user_id = ? WHERE user_id IS NULL', (DEFAULT_USER_ID,))
            wishlist_count = cursor.rowcount
            print(f"✓ Updated {wishlist_count} wishlist records")
            
            # Update existing price_alerts data
            cursor.execute('UPDATE price_alerts SET user_id = ? WHERE user_id IS NULL', (DEFAULT_USER_ID,))
            alerts_count = cursor.rowcount
            print(f"✓ Updated {alerts_count} price alert records")
            
            # Update existing search_history data
            cursor.execute('UPDATE search_history SET user_id = ? WHERE user_id IS NULL', (DEFAULT_USER_ID,))
            search_count = cursor.rowcount
            print(f"✓ Updated {search_count} search history records")
            
            # Update existing price_history data
            cursor.execute('UPDATE price_history SET user_id = ? WHERE user_id IS NULL', (DEFAULT_USER_ID,))
            price_count = cursor.rowcount
            print(f"✓ Updated {price_count} price history records")
            
            print("\nCreating indexes for better performance...")
            
            # Create indexes for user_id columns
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_wishlist_user_id ON wishlist(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_alerts_user_id ON price_alerts(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON search_history(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_user_id ON price_history(user_id)')
                print("✓ Created indexes for user_id columns")
            except Exception as e:
                print(f"Warning: Could not create indexes: {e}")
            
            conn.commit()
            
            print(f"\n✅ Migration completed successfully!")
            print(f"📊 Summary:")
            print(f"   - Feedback records: {feedback_count}")
            print(f"   - Wishlist records: {wishlist_count}")
            print(f"   - Price alerts: {alerts_count}")
            print(f"   - Search history: {search_count}")
            print(f"   - Price history: {price_count}")
            print(f"   - Total records migrated: {feedback_count + wishlist_count + alerts_count + search_count + price_count}")
            print(f"\n⚠️  Note: All existing data has been assigned to user ID: {DEFAULT_USER_ID}")
            print(f"   New users will get their own unique user IDs automatically.")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    migrate_database()
