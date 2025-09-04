#!/usr/bin/env python3
"""
Personal AI News Feed - Local Proof of Concept v2.0
Security-focused news aggregation and summarization system with configuration file support
"""

import feedparser
import requests
from datetime import datetime, timedelta
import sqlite3
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import List, Dict, Tuple, Optional
import re
import json
from dataclasses import dataclass
from pathlib import Path
import time
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('news_feed.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class NewsArticle:
    title: str
    summary: str
    url: str
    published: datetime
    category: str
    source: str
    content_hash: str
    fact_speculation_analysis: str = ""

@dataclass
class NewsSource:
    name: str
    url: str
    enabled: bool
    note: str = ""

class ConfigManager:
    """Manage configuration from JSON file"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logging.info(f"Configuration loaded from {self.config_path}")
            return config
        except FileNotFoundError:
            logging.warning(f"Config file {self.config_path} not found, using defaults")
            return self.get_default_config()
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in config file: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> dict:
        """Return default configuration"""
        return {
            "database": {"path": "news_feed.db", "cleanup_days": 30},
            "collection": {"article_age_limit_days": 2, "request_timeout": 30, "rate_limit_delay": 1},
            "analysis": {
                "fact_keywords": ["announced", "confirmed", "disclosed"],
                "speculation_keywords": ["allegedly", "reportedly", "sources say"]
            },
            "news_sources": {},
            "report": {"filename_pattern": "news_report_{date}.html", "title": "Personal News Digest"}
        }
    
    def get_enabled_sources(self) -> Dict[str, List[NewsSource]]:
        """Get enabled news sources by category"""
        sources = {}
        for category, source_list in self.config.get("news_sources", {}).items():
            enabled_sources = []
            for source_data in source_list:
                if source_data.get("enabled", True):
                    source = NewsSource(
                        name=source_data["name"],
                        url=source_data["url"],
                        enabled=source_data.get("enabled", True),
                        note=source_data.get("note", "")
                    )
                    enabled_sources.append(source)
            if enabled_sources:
                sources[category] = enabled_sources
        return sources

class NewsDatabase:
    """Secure local database for article storage"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.db_path = config.config.get("database", {}).get("path", "news_feed.db")
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with security considerations"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
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
        
        # Create index for performance and deduplication
        conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON articles(content_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_published ON articles(published)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON articles(url)")
        conn.commit()
        conn.close()
    
    def article_exists(self, content_hash: str) -> bool:
        """Check if article already processed by content hash"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT 1 FROM articles WHERE content_hash = ?", (content_hash,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def url_exists(self, url: str) -> bool:
        """Check if article URL already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def save_article(self, article: NewsArticle):
        """Save article to database with duplicate handling"""
        if self.article_exists(article.content_hash):
            logging.info(f"Article already exists (content): {article.title[:50]}...")
            return
        
        if self.url_exists(article.url):
            logging.info(f"Article already exists (URL): {article.title[:50]}...")
            return
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO articles 
                (title, summary, url, published, category, source, content_hash, fact_speculation_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.title, article.summary, article.url, article.published,
                article.category, article.source, article.content_hash, article.fact_speculation_analysis
            ))
            conn.commit()
            logging.info(f"Saved article: {article.title[:50]}...")
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: articles.url" in str(e):
                logging.info(f"Article URL already exists: {article.title[:50]}...")
            elif "UNIQUE constraint failed: articles.content_hash" in str(e):
                logging.info(f"Article content already exists: {article.title[:50]}...")
            else:
                logging.error(f"Database integrity error: {e}")
                raise
        finally:
            conn.close()
    
    def get_recent_articles(self, hours: int = 24) -> List[NewsArticle]:
        """Get articles from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT title, summary, url, published, category, source, content_hash, fact_speculation_analysis
            FROM articles 
            WHERE published > ?
            ORDER BY published DESC
        """, (cutoff,))
        
        articles = []
        for row in cursor.fetchall():
            # Convert string back to datetime if needed
            published = row[3]
            if isinstance(published, str):
                try:
                    published = datetime.fromisoformat(published.replace('Z', '+00:00'))
                except ValueError:
                    published = datetime.now()
            
            article = NewsArticle(
                title=row[0],
                summary=row[1], 
                url=row[2],
                published=published,
                category=row[4],
                source=row[5],
                content_hash=row[6],
                fact_speculation_analysis=row[7]
            )
            articles.append(article)
        
        conn.close()
        return articles
    
    def cleanup_old_articles(self, days: Optional[int] = None):
        """Remove articles older than N days for privacy"""
        if days is None:
            days = self.config.config.get("database", {}).get("cleanup_days", 30)
        
        cutoff = datetime.now() - timedelta(days=days)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM articles WHERE published < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        logging.info(f"Cleaned up {deleted} old articles")

class NewsCollector:
    """Collect news from RSS feeds and APIs"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Personal-News-Aggregator/2.0'
        })
        
        # Get timeout from config
        self.timeout = config.config.get("collection", {}).get("request_timeout", 30)
        self.rate_limit = config.config.get("collection", {}).get("rate_limit_delay", 1)
        self.age_limit = config.config.get("collection", {}).get("article_age_limit_days", 2)
    
    def fetch_rss_feed(self, source: NewsSource, category: str) -> List[NewsArticle]:
        """Fetch and parse RSS feed"""
        articles = []
        try:
            logging.info(f"Fetching {source.name} ({source.url})...")
            response = self.session.get(source.url, timeout=self.timeout)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            source_title = feed.feed.get('title', source.name)
            
            for entry in feed.entries:
                # Create content hash for deduplication
                content_for_hash = f"{entry.title}{entry.get('summary', '')}"
                content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
                
                # Parse publication date
                published = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except (TypeError, ValueError):
                        # Fallback to current time if parsing fails
                        published = datetime.now()
                
                # Only process recent articles
                if published > datetime.now() - timedelta(days=self.age_limit):
                    article = NewsArticle(
                        title=entry.title,
                        summary=entry.get('summary', ''),
                        url=entry.link,
                        published=published,
                        category=category,
                        source=source_title,
                        content_hash=content_hash
                    )
                    articles.append(article)
            
            logging.info(f"Fetched {len(articles)} recent articles from {source_title}")
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching {source.url}: {str(e)}")
        except Exception as e:
            logging.error(f"Error processing feed {source.url}: {str(e)}")
        
        return articles
    
    def collect_all_news(self) -> List[NewsArticle]:
        """Collect news from all configured sources"""
        all_articles = []
        
        sources = self.config.get_enabled_sources()
        for category, source_list in sources.items():
            for source in source_list:
                articles = self.fetch_rss_feed(source, category)
                all_articles.extend(articles)
                time.sleep(self.rate_limit)  # Rate limiting - be respectful
        
        return all_articles

class ConfigurableAnalyzer:
    """Configurable text analysis"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        # Get keywords from config
        analysis_config = config.config.get("analysis", {})
        self.speculation_keywords = analysis_config.get("speculation_keywords", [])
        self.fact_keywords = analysis_config.get("fact_keywords", [])
    
    def analyze_content(self, article: NewsArticle) -> str:
        """Fact vs speculation analysis using configured keywords"""
        text = (article.title + " " + article.summary).lower()
        
        speculation_count = sum(1 for keyword in self.speculation_keywords if keyword in text)
        fact_count = sum(1 for keyword in self.fact_keywords if keyword in text)
        
        if speculation_count > fact_count:
            return "SPECULATION"
        elif fact_count > speculation_count:
            return "FACTUAL"
        else:
            return "MIXED"
    
    def create_summary(self, article: NewsArticle) -> str:
        """Create a brief summary"""
        max_length = self.config.config.get("report", {}).get("max_summary_length", 200)
        summary = article.summary[:max_length] + "..." if len(article.summary) > max_length else article.summary
        
        # Remove HTML tags
        summary = re.sub('<[^<]+?>', '', summary)
        
        return summary

class EmailReporter:
    """Generate and send email reports"""
    
    def __init__(self, config: ConfigManager, smtp_config: Dict = None):
        self.config = config
        self.smtp_config = smtp_config or {}
    
    def generate_report(self, articles: List[NewsArticle]) -> str:
        """Generate HTML email report"""
        # Group articles by category
        categorized = {}
        for article in articles:
            if article.category not in categorized:
                categorized[article.category] = []
            categorized[article.category].append(article)
        
        # Generate report 
        report_title = self.config.config.get("report", {}).get("title", "Personal News Digest")
        report_date = datetime.now().strftime("%A, %B %d")
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .header {{ background-color: #2c3e50; color: white; padding: 15px; }}
                .category {{ margin: 20px 0; }}
                .article {{ margin: 10px 0; padding: 10px; border-left: 3px solid #3498db; }}
                .fact {{ border-left-color: #27ae60; }}
                .speculation {{ border-left-color: #e74c3c; }}
                .mixed {{ border-left-color: #f39c12; }}
                .source {{ font-size: 0.9em; color: #666; }}
                .analysis {{ font-weight: bold; font-size: 0.8em; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{report_title}: {report_date}</h1>
                <p>Total Articles: {len(articles)}</p>
            </div>
        """
        
        # Add takeaways section (top stories)
        html_content += "<h2>Today's Top Takeaways:</h2><ul>"
        
        # Get top story from each category
        for category, cat_articles in categorized.items():
            if cat_articles:
                top_article = sorted(cat_articles, key=lambda x: x.published, reverse=True)[0]
                html_content += f"<li><strong>{category.title().replace('_', ' ')}:</strong> {top_article.title}</li>"
        
        html_content += "</ul><hr>"
        
        # Add articles by category
        for category, cat_articles in categorized.items():
            if not cat_articles:
                continue
                
            html_content += f'<div class="category"><h2>{category.title().replace("_", " ")}</h2>'
            
            for article in sorted(cat_articles, key=lambda x: x.published, reverse=True):
                analysis_class = article.fact_speculation_analysis.lower()
                html_content += f'''
                <div class="article {analysis_class}">
                    <h3><a href="{article.url}" target="_blank">{article.title}</a></h3>
                    <p>{article.summary}</p>
                    <div class="source">Source: {article.source} | Published: {article.published.strftime("%H:%M")}</div>
                    <div class="analysis">Analysis: {article.fact_speculation_analysis}</div>
                </div>
                '''
            
            html_content += '</div>'
        
        html_content += "</body></html>"
        return html_content
    
    def save_report(self, content: str, filename: str = None):
        """Save report to file for review"""
        if not filename:
            pattern = self.config.config.get("report", {}).get("filename_pattern", "news_report_{date}.html")
            filename = pattern.format(date=datetime.now().strftime('%Y%m%d'))
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info(f"Report saved to {filename}")

class NewsAggregator:
    """Main orchestrator class"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = ConfigManager(config_path)
        self.db = NewsDatabase(self.config)
        self.collector = NewsCollector(self.config)
        self.analyzer = ConfigurableAnalyzer(self.config)
        self.reporter = EmailReporter(self.config)
    
    def run_daily_collection(self):
        """Run the daily news collection and analysis"""
        logging.info("Starting daily news collection...")
        
        # Clean up old articles first
        self.db.cleanup_old_articles()
        
        # Collect new articles
        articles = self.collector.collect_all_news()
        logging.info(f"Collected {len(articles)} articles")
        
        # Process and analyze each article
        processed = 0
        for article in articles:
            # Check for duplicates by both content hash and URL
            if not self.db.article_exists(article.content_hash) and not self.db.url_exists(article.url):
                # Analyze content
                article.fact_speculation_analysis = self.analyzer.analyze_content(article)
                article.summary = self.analyzer.create_summary(article)
                
                # Save to database
                self.db.save_article(article)
                processed += 1
            else:
                logging.debug(f"Duplicate article skipped: {article.title[:50]}...")
        
        logging.info(f"Processed {processed} new articles")
        
        # Generate report
        recent_articles = self.db.get_recent_articles(24)
        if recent_articles:
            report_content = self.reporter.generate_report(recent_articles)
            self.reporter.save_report(report_content)
            logging.info("Daily report generated successfully")
        else:
            logging.info("No recent articles to report")
    
    def show_status(self):
        """Show current configuration and database status"""
        print("Personal AI News Feed - Status")
        print("=" * 50)
        
        # Show enabled sources
        sources = self.config.get_enabled_sources()
        total_sources = sum(len(source_list) for source_list in sources.values())
        print(f"Enabled news sources: {total_sources}")
        
        for category, source_list in sources.items():
            print(f"\n  {category.title()}:")
            for source in source_list:
                status = "✅" if source.enabled else "❌"
                print(f"    {status} {source.name}")
                if source.note:
                    print(f"       Note: {source.note}")
        
        # Show database stats
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor = conn.execute("""
                SELECT category, COUNT(*) 
                FROM articles 
                GROUP BY category 
                ORDER BY COUNT(*) DESC
            """)
            categories = cursor.fetchall()
            conn.close()
            
            print(f"\nDatabase: {total_articles} articles")
            for category, count in categories:
                print(f"  {category}: {count}")
                
        except Exception as e:
            print(f"Database error: {e}")

def main():
    """Main entry point"""
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            aggregator = NewsAggregator()
            aggregator.show_status()
            return
        elif sys.argv[1] == "config":
            print("Configuration file: config.json")
            print("Edit this file to customize news sources and settings.")
            return
    
    aggregator = NewsAggregator()
    
    try:
        aggregator.run_daily_collection()
    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()