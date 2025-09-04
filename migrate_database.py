#!/usr/bin/env python3
"""
Database Migration Script for Personal News Aggregator
Safely updates existing database schema to v3.0 format
"""

import sqlite3
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def migrate_database(db_path: str = "news_feed.db"):
    """Migrate existing database to new schema"""
    
    if not Path(db_path).exists():
        logging.info(f"Database {db_path} doesn't exist - will be created on first run")
        return True
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check if table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
        if not cursor.fetchone():
            logging.info("No articles table found - clean database")
            conn.close()
            return True
        
        # Get current columns
        cursor = conn.execute("PRAGMA table_info(articles)")
        existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        logging.info(f"Current columns: {list(existing_columns.keys())}")
        
        # Define new columns to add
        new_columns = {
            'importance_score': 'INTEGER DEFAULT 0',
            'key_highlights': 'TEXT',
            'full_content': 'TEXT', 
            'author': 'TEXT',
            'duplicate_group': 'INTEGER'
        }
        
        # Add missing columns
        columns_added = []
        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
                    columns_added.append(col_name)
                    logging.info(f"Added column: {col_name}")
                except sqlite3.OperationalError as e:
                    logging.error(f"Error adding column {col_name}: {e}")
                    continue
        
        if columns_added:
            logging.info(f"Successfully added {len(columns_added)} new columns")
        else:
            logging.info("Database schema is already up to date")
        
        # Create new indexes safely
        indexes_to_create = [
            ("idx_importance", "importance_score"),
            ("idx_duplicate_group", "duplicate_group"),
            ("idx_content_hash", "content_hash"),
            ("idx_published", "published"),
            ("idx_url", "url")
        ]
        
        for index_name, column_name in indexes_to_create:
            if column_name in existing_columns or column_name in columns_added:
                try:
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON articles({column_name})")
                    logging.debug(f"Created index: {index_name}")
                except sqlite3.OperationalError as e:
                    logging.warning(f"Could not create index {index_name}: {e}")
        
        conn.commit()
        conn.close()
        
        logging.info("Database migration completed successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Database migration failed: {e}")
        return False

def verify_database(db_path: str = "news_feed.db"):
    """Verify database schema after migration"""
    
    if not Path(db_path).exists():
        logging.info("Database file doesn't exist yet")
        return True
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Check table structure
        cursor = conn.execute("PRAGMA table_info(articles)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        required_columns = [
            'id', 'title', 'summary', 'url', 'published', 'category', 
            'source', 'content_hash', 'fact_speculation_analysis',
            'importance_score', 'key_highlights', 'full_content', 
            'author', 'duplicate_group', 'created_at'
        ]
        
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            logging.error(f"Missing columns after migration: {missing_columns}")
            conn.close()
            return False
        
        # Check indexes
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='articles'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        logging.info(f"Database verification successful!")
        logging.info(f"Total columns: {len(columns)}")
        logging.info(f"Total indexes: {len(indexes)}")
        
        return True
        
    except Exception as e:
        logging.error(f"Database verification failed: {e}")
        return False

def backup_database(db_path: str = "news_feed.db"):
    """Create backup of existing database"""
    
    if not Path(db_path).exists():
        logging.info("No database to backup")
        return True
    
    try:
        from datetime import datetime
        import shutil
        
        backup_name = f"news_feed_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(db_path, backup_name)
        
        logging.info(f"Database backed up to: {backup_name}")
        return True
        
    except Exception as e:
        logging.error(f"Database backup failed: {e}")
        return False

def main():
    """Main migration function"""
    
    print("Personal News Aggregator - Database Migration Tool")
    print("=" * 50)
    
    # Load config to get database path
    db_path = "news_feed.db"
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
            db_path = config.get("database", {}).get("path", "news_feed.db")
    except FileNotFoundError:
        logging.info("No config.json found, using default database path")
    except json.JSONDecodeError:
        logging.warning("Invalid config.json, using default database path")
    
    print(f"Database path: {db_path}")
    
    # Create backup
    print("\n1. Creating backup...")
    if not backup_database(db_path):
        print("   ❌ Backup failed - stopping migration")
        return False
    print("   ✅ Backup completed")
    
    # Migrate database
    print("\n2. Migrating database schema...")
    if not migrate_database(db_path):
        print("   ❌ Migration failed")
        return False
    print("   ✅ Migration completed")
    
    # Verify migration
    print("\n3. Verifying database...")
    if not verify_database(db_path):
        print("   ❌ Verification failed")
        return False
    print("   ✅ Verification completed")
    
    print("\n🎉 Database migration successful!")
    print("\nYou can now run: python news_feed.py status")
    
    return True

if __name__ == "__main__":
    main()