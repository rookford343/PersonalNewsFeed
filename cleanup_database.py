#!/usr/bin/env python3
"""
Database cleanup script for Personal AI News Feed
Use this to fix duplicate articles and database inconsistencies
"""

import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def analyze_database(db_path="news_feed.db"):
    """Analyze database for duplicates and issues"""
    print(f"Analyzing database: {db_path}")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    
    # Check total articles
    cursor = conn.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]
    print(f"Total articles: {total_articles}")
    
    # Check for URL duplicates
    cursor = conn.execute("""
        SELECT url, COUNT(*) as count 
        FROM articles 
        GROUP BY url 
        HAVING count > 1
        ORDER BY count DESC
    """)
    url_duplicates = cursor.fetchall()
    print(f"Duplicate URLs: {len(url_duplicates)}")
    
    if url_duplicates:
        print("\nTop URL duplicates:")
        for url, count in url_duplicates[:5]:
            print(f"  {count}x: {url[:80]}...")
    
    # Check for content hash duplicates
    cursor = conn.execute("""
        SELECT content_hash, COUNT(*) as count 
        FROM articles 
        GROUP BY content_hash 
        HAVING count > 1
        ORDER BY count DESC
    """)
    hash_duplicates = cursor.fetchall()
    print(f"Duplicate content hashes: {len(hash_duplicates)}")
    
    # Articles by category
    cursor = conn.execute("""
        SELECT category, COUNT(*) as count 
        FROM articles 
        GROUP BY category 
        ORDER BY count DESC
    """)
    categories = cursor.fetchall()
    print(f"\nArticles by category:")
    for category, count in categories:
        print(f"  {category}: {count}")
    
    # Recent articles (last 24 hours)
    cursor = conn.execute("""
        SELECT COUNT(*) FROM articles 
        WHERE datetime(published) > datetime('now', '-1 day')
    """)
    recent_count = cursor.fetchone()[0]
    print(f"\nRecent articles (24h): {recent_count}")
    
    conn.close()
    return len(url_duplicates) > 0 or len(hash_duplicates) > 0

def cleanup_duplicates(db_path="news_feed.db", dry_run=True):
    """Remove duplicate articles, keeping the most recent"""
    print(f"\nCleaning up duplicates (dry_run={dry_run})")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    
    # Remove URL duplicates, keep most recent
    cursor = conn.execute("""
        SELECT url, COUNT(*) as count 
        FROM articles 
        GROUP BY url 
        HAVING count > 1
    """)
    
    duplicate_urls = [row[0] for row in cursor.fetchall()]
    removed_count = 0
    
    for url in duplicate_urls:
        # Get all articles with this URL, ordered by date
        cursor = conn.execute("""
            SELECT id, title, published 
            FROM articles 
            WHERE url = ?
            ORDER BY datetime(published) DESC
        """, (url,))
        
        articles = cursor.fetchall()
        if len(articles) > 1:
            # Keep the first (most recent), remove the rest
            keep_id = articles[0][0]
            remove_ids = [article[0] for article in articles[1:]]
            
            print(f"URL duplicate: {url[:60]}...")
            print(f"  Keeping: {articles[0][1][:40]}... (ID: {keep_id})")
            print(f"  Removing {len(remove_ids)} older copies")
            
            if not dry_run:
                for remove_id in remove_ids:
                    conn.execute("DELETE FROM articles WHERE id = ?", (remove_id,))
                removed_count += len(remove_ids)
    
    if not dry_run:
        conn.commit()
        print(f"\nRemoved {removed_count} duplicate articles")
    else:
        print(f"\nWould remove {removed_count} duplicate articles")
    
    conn.close()
    return removed_count

def reset_database(db_path="news_feed.db"):
    """Completely reset the database (use with caution!)"""
    response = input(f"\n⚠️  WARNING: This will delete ALL articles from {db_path}. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Database reset cancelled.")
        return False
    
    print("Resetting database...")
    conn = sqlite3.connect(db_path)
    
    # Drop and recreate tables
    conn.execute("DROP TABLE IF EXISTS articles")
    conn.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT UNIQUE NOT NULL,
            published DATETIME,
            category TEXT,
            source TEXT,
            content_hash TEXT UNIQUE,
            fact_speculation_analysis TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Recreate indexes
    conn.execute("CREATE INDEX idx_content_hash ON articles(content_hash)")
    conn.execute("CREATE INDEX idx_published ON articles(published)")
    
    conn.commit()
    conn.close()
    
    print("✅ Database reset complete!")
    return True

def main():
    """Main cleanup interface"""
    print("Personal AI News Feed - Database Cleanup Tool")
    print("=" * 50)
    print(f"Started at: {datetime.now()}")
    
    # Analyze current state
    has_duplicates = analyze_database()
    
    if not has_duplicates:
        print("\n✅ No duplicates found! Database looks clean.")
        return
    
    print("\n🔧 Cleanup Options:")
    print("1. Preview cleanup (dry run)")
    print("2. Clean up duplicates") 
    print("3. Reset entire database")
    print("4. Exit")
    
    while True:
        try:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                cleanup_duplicates(dry_run=True)
                break
            elif choice == '2':
                removed = cleanup_duplicates(dry_run=False)
                if removed > 0:
                    print("\n✅ Cleanup complete! Re-analyzing...")
                    analyze_database()
                break
            elif choice == '3':
                reset_database()
                break
            elif choice == '4':
                print("Exiting without changes.")
                break
            else:
                print("Invalid choice. Please select 1-4.")
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break

if __name__ == "__main__":
    main()