#!/usr/bin/env python3
"""
 Personal News Feed - v3.0
Secure news aggregation with email delivery, improved analysis, and scheduling
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
from dataclasses import dataclass, field
from pathlib import Path
import time
import os
import schedule
import argparse
from collections import Counter
import ssl
from email.utils import formataddr
import keyring  # For secure credential storage
import getpass

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
    importance_score: int = 0
    key_highlights: List[str] = field(default_factory=list)
    full_content: str = ""
    author: str = ""

@dataclass
class NewsSource:
    name: str
    url: str
    enabled: bool
    note: str = ""
    priority: int = 1  # 1-5, higher = more important

class SecureCredentialManager:
    """Secure credential management using keyring"""
    
    @staticmethod
    def set_email_credentials(email: str, password: str, smtp_server: str, smtp_port: int):
        """Securely store email credentials"""
        try:
            keyring.set_password("news_aggregator_smtp", email, password)
            keyring.set_password("news_aggregator_config", "smtp_server", smtp_server)
            keyring.set_password("news_aggregator_config", "smtp_port", str(smtp_port))
            keyring.set_password("news_aggregator_config", "email", email)
            logging.info("Email credentials stored securely")
        except Exception as e:
            logging.error(f"Failed to store credentials: {e}")
    
    @staticmethod
    def get_email_credentials() -> Optional[Dict[str, str]]:
        """Retrieve stored email credentials"""
        try:
            email = keyring.get_password("news_aggregator_config", "email")
            if not email:
                return None
            
            password = keyring.get_password("news_aggregator_smtp", email)
            smtp_server = keyring.get_password("news_aggregator_config", "smtp_server")
            smtp_port = keyring.get_password("news_aggregator_config", "smtp_port")
            
            if all([password, smtp_server, smtp_port]):
                return {
                    "email": email,
                    "password": password,
                    "smtp_server": smtp_server,
                    "smtp_port": int(smtp_port)
                }
        except Exception as e:
            logging.error(f"Failed to retrieve credentials: {e}")
        
        return None

class ConfigManager:
    """ configuration management"""
    
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
            logging.warning(f"Config file {self.config_path} not found, creating default")
            default_config = self.get_default_config()
            self.save_config(default_config)
            return default_config
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in config file: {e}")
            return self.get_default_config()
    
    def save_config(self, config: dict):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logging.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logging.error(f"Failed to save config: {e}")
    
    def get_default_config(self) -> dict:
        """Return  default configuration"""
        return {
            "database": {
                "path": "news_feed.db",
                "cleanup_days": 30
            },
            "collection": {
                "article_age_limit_days": 2,
                "request_timeout": 30,
                "rate_limit_delay": 1,
                "max_articles_per_source": 50
            },
            "analysis": {
                "fact_keywords": [
                    "announced", "confirmed", "disclosed", "reported earnings",
                    "filed", "released", "published", "data shows", "statistics",
                    "according to", "statement", "press release", "official"
                ],
                "speculation_keywords": [
                    "allegedly", "reportedly", "sources say", "rumors", "speculation",
                    "could", "might", "may", "possible", "potential", "unconfirmed",
                    "according to sources", "insider claims", "expected", "likely"
                ],
                "importance_keywords": [
                    "breaking", "urgent", "critical", "major", "significant",
                    "emergency", "alert", "exclusive", "developing"
                ],
                "enable_duplicate_detection": True,
                "duplicate_similarity_threshold": 0.8
            },
            "email": {
                "enabled": False,
                "recipient": "",
                "subject_template": "Daily News Digest - {date}",
                "send_time": "08:00",
                "include_attachments": False
            },
            "scheduling": {
                "enabled": False,
                "collection_times": ["08:00", "18:00"],
                "report_time": "08:30"
            },
            "report": {
                "filename_pattern": "news_report_{date}.html",
                "title": " Personal News Digest",
                "max_summary_length": 300,
                "show_full_content": False,
                "highlight_duplicates": True,
                "group_by_importance": True,
                "max_articles_per_category": 20
            },
            "news_sources": {
                "cybersecurity": [
                    {
                        "name": "Krebs on Security",
                        "url": "https://krebsonsecurity.com/feed/",
                        "enabled": True,
                        "priority": 5
                    },
                    {
                        "name": "Dark Reading",
                        "url": "https://www.darkreading.com/rss.xml",
                        "enabled": True,
                        "priority": 4
                    }
                ]
            }
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
                        note=source_data.get("note", ""),
                        priority=source_data.get("priority", 1)
                    )
                    enabled_sources.append(source)
            if enabled_sources:
                sources[category] = enabled_sources
        return sources

class NewsDatabase:
    """ database with duplicate detection and importance scoring"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.db_path = config.config.get("database", {}).get("path", "news_feed.db")
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with  schema"""
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
                content_hash TEXT,
                fact_speculation_analysis TEXT,
                importance_score INTEGER DEFAULT 0,
                key_highlights TEXT, -- JSON array
                full_content TEXT,
                author TEXT,
                duplicate_group INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(content_hash) ON CONFLICT IGNORE
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON articles(content_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_published ON articles(published)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON articles(importance_score)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_group ON articles(duplicate_group)")
        conn.commit()
        conn.close()
    
    def find_similar_articles(self, article: NewsArticle) -> List[int]:
        """Find similar articles using simple text similarity"""
        if not self.config.config.get("analysis", {}).get("enable_duplicate_detection", True):
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT id, title, summary FROM articles 
            WHERE published > ? AND category = ?
        """, (datetime.now() - timedelta(days=7), article.category))
        
        similar_articles = []
        article_text = (article.title + " " + article.summary).lower()
        words = set(re.findall(r'\w+', article_text))
        
        for row in cursor.fetchall():
            existing_text = (row[1] + " " + (row[2] or "")).lower()
            existing_words = set(re.findall(r'\w+', existing_text))
            
            # Calculate Jaccard similarity
            if words and existing_words:
                similarity = len(words & existing_words) / len(words | existing_words)
                threshold = self.config.config.get("analysis", {}).get("duplicate_similarity_threshold", 0.8)
                
                if similarity > threshold:
                    similar_articles.append(row[0])
        
        conn.close()
        return similar_articles
    
    def save_article(self, article: NewsArticle):
        """Save article with duplicate detection and grouping"""
        if self.url_exists(article.url):
            logging.info(f"Article already exists (URL): {article.title[:50]}...")
            return
        
        # Find similar articles
        similar_ids = self.find_similar_articles(article)
        
        conn = sqlite3.connect(self.db_path)
        try:
            # Determine duplicate group
            duplicate_group = None
            if similar_ids:
                # Get existing duplicate group or create new one
                cursor = conn.execute(
                    "SELECT DISTINCT duplicate_group FROM articles WHERE id IN ({})".format(
                        ','.join('?' * len(similar_ids))
                    ), similar_ids
                )
                existing_groups = [row[0] for row in cursor.fetchall() if row[0]]
                
                if existing_groups:
                    duplicate_group = existing_groups[0]
                    # Update importance score based on duplicate count
                    article.importance_score += len(similar_ids) * 10
                else:
                    # Create new duplicate group
                    cursor = conn.execute("SELECT MAX(duplicate_group) FROM articles")
                    max_group = cursor.fetchone()[0] or 0
                    duplicate_group = max_group + 1
                    
                    # Update similar articles with new group
                    conn.execute(f"""
                        UPDATE articles SET duplicate_group = ? 
                        WHERE id IN ({','.join('?' * len(similar_ids))})
                    """, [duplicate_group] + similar_ids)
            
            # Insert new article
            conn.execute("""
                INSERT INTO articles 
                (title, summary, url, published, category, source, content_hash, 
                 fact_speculation_analysis, importance_score, key_highlights, 
                 full_content, author, duplicate_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.title, article.summary, article.url, article.published,
                article.category, article.source, article.content_hash,
                article.fact_speculation_analysis, article.importance_score,
                json.dumps(article.key_highlights), article.full_content,
                article.author, duplicate_group
            ))
            conn.commit()
            logging.info(f"Saved article: {article.title[:50]}... (Importance: {article.importance_score})")
            
        except sqlite3.IntegrityError as e:
            logging.info(f"Duplicate article skipped: {article.title[:50]}...")
        finally:
            conn.close()
    
    def url_exists(self, url: str) -> bool:
        """Check if article URL already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def get_recent_articles(self, hours: int = 24) -> List[NewsArticle]:
        """Get recent articles with  data"""
        cutoff = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT title, summary, url, published, category, source, content_hash, 
                   fact_speculation_analysis, importance_score, key_highlights, 
                   full_content, author, duplicate_group
            FROM articles 
            WHERE published > ?
            ORDER BY importance_score DESC, published DESC
        """, (cutoff,))
        
        articles = []
        for row in cursor.fetchall():
            published = row[3]
            if isinstance(published, str):
                try:
                    published = datetime.fromisoformat(published.replace('Z', '+00:00'))
                except ValueError:
                    published = datetime.now()
            
            key_highlights = []
            try:
                if row[9]:
                    key_highlights = json.loads(row[9])
            except json.JSONDecodeError:
                pass
            
            article = NewsArticle(
                title=row[0],
                summary=row[1],
                url=row[2],
                published=published,
                category=row[4],
                source=row[5],
                content_hash=row[6],
                fact_speculation_analysis=row[7],
                importance_score=row[8],
                key_highlights=key_highlights,
                full_content=row[10] or "",
                author=row[11] or ""
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
    
    def get_duplicate_groups(self, hours: int = 24) -> Dict[int, List[NewsArticle]]:
        """Get articles grouped by duplicate groups"""
        articles = self.get_recent_articles(hours)
        groups = {}
        
        for article in articles:
            # Check if article is part of a duplicate group
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT duplicate_group FROM articles WHERE content_hash = ?",
                (article.content_hash,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                group_id = result[0]
                if group_id not in groups:
                    groups[group_id] = []
                groups[group_id].append(article)
        
        return groups

class NewsCollector:
    """ news collector with better content extraction"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Personal-News-Aggregator/3.0 (+https://example.com/bot)'
        })
        
        self.timeout = config.config.get("collection", {}).get("request_timeout", 30)
        self.rate_limit = config.config.get("collection", {}).get("rate_limit_delay", 1)
        self.age_limit = config.config.get("collection", {}).get("article_age_limit_days", 2)
        self.max_articles = config.config.get("collection", {}).get("max_articles_per_source", 50)
    
    def extract_full_content(self, url: str) -> str:
        """Attempt to extract full article content (basic implementation)"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Basic content extraction - remove HTML tags
            content = re.sub(r'<script.*?</script>', '', response.text, flags=re.DOTALL)
            content = re.sub(r'<style.*?</style>', '', content, flags=re.DOTALL)
            content = re.sub(r'<[^>]+>', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()
            
            # Return first 2000 characters as a basic summary
            return content[:2000] + "..." if len(content) > 2000 else content
            
        except Exception as e:
            logging.debug(f"Could not extract full content from {url}: {e}")
            return ""
    
    def fetch_rss_feed(self, source: NewsSource, category: str) -> List[NewsArticle]:
        """ RSS feed fetching with content extraction"""
        articles = []
        try:
            logging.info(f"Fetching {source.name} ({source.url})...")
            response = self.session.get(source.url, timeout=self.timeout)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            source_title = feed.feed.get('title', source.name)
            
            processed_count = 0
            for entry in feed.entries:
                if processed_count >= self.max_articles:
                    break
                
                # Create content hash for deduplication
                content_for_hash = f"{entry.title}{entry.get('summary', '')}"
                content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
                
                # Parse publication date
                published = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except (TypeError, ValueError):
                        published = datetime.now()
                
                # Only process recent articles
                if published > datetime.now() - timedelta(days=self.age_limit):
                    # Extract author
                    author = entry.get('author', '')
                    
                    # Get full content if enabled
                    full_content = ""
                    if self.config.config.get("report", {}).get("show_full_content", False):
                        full_content = self.extract_full_content(entry.link)
                    
                    article = NewsArticle(
                        title=entry.title,
                        summary=entry.get('summary', ''),
                        url=entry.link,
                        published=published,
                        category=category,
                        source=source_title,
                        content_hash=content_hash,
                        full_content=full_content,
                        author=author
                    )
                    
                    # Add source priority to importance score
                    article.importance_score += source.priority * 5
                    
                    articles.append(article)
                    processed_count += 1
            
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
            # Sort sources by priority
            source_list.sort(key=lambda s: s.priority, reverse=True)
            
            for source in source_list:
                articles = self.fetch_rss_feed(source, category)
                all_articles.extend(articles)
                time.sleep(self.rate_limit)
        
        return all_articles

class Analyzer:
    """ analysis with importance scoring and highlights"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        analysis_config = config.config.get("analysis", {})
        self.speculation_keywords = analysis_config.get("speculation_keywords", [])
        self.fact_keywords = analysis_config.get("fact_keywords", [])
        self.importance_keywords = analysis_config.get("importance_keywords", [])
    
    def calculate_importance_score(self, article: NewsArticle) -> int:
        """Calculate article importance based on various factors"""
        score = article.importance_score  # Base score from source priority
        
        text = (article.title + " " + article.summary).lower()
        
        # Check for importance keywords
        for keyword in self.importance_keywords:
            if keyword in text:
                score += 20
        
        # Boost score for cybersecurity articles (given user's role)
        if article.category == "cybersecurity":
            score += 15
        
        # Boost recent articles
        hours_old = (datetime.now() - article.published).total_seconds() / 3600
        if hours_old < 6:
            score += 10
        elif hours_old < 12:
            score += 5
        
        # Boost based on content length (more detailed = potentially more important)
        if len(article.summary) > 500:
            score += 5
        
        return max(0, score)
    
    def extract_key_highlights(self, article: NewsArticle) -> List[str]:
        """Extract key highlights from article content"""
        highlights = []
        
        # Combine title and summary for analysis
        text = article.title + ". " + article.summary
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Find sentences with important keywords
        important_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for keyword in self.importance_keywords + self.fact_keywords:
                if keyword in sentence_lower and len(sentence) < 200:
                    important_sentences.append(sentence)
                    break
        
        # Take first 3 important sentences or first 3 sentences if none found
        highlights = important_sentences[:3] if important_sentences else sentences[:3]
        
        # Clean up highlights
        highlights = [re.sub(r'\s+', ' ', h).strip() for h in highlights]
        highlights = [h for h in highlights if len(h) > 10]
        
        return highlights[:3]  # Maximum 3 highlights
    
    def analyze_content(self, article: NewsArticle) -> str:
        """ fact vs speculation analysis"""
        text = (article.title + " " + article.summary).lower()
        
        speculation_count = sum(1 for keyword in self.speculation_keywords if keyword in text)
        fact_count = sum(1 for keyword in self.fact_keywords if keyword in text)
        
        # More nuanced analysis
        if speculation_count > fact_count + 1:
            return "SPECULATION"
        elif fact_count > speculation_count + 1:
            return "FACTUAL"
        elif speculation_count == fact_count == 0:
            return "NEUTRAL"
        else:
            return "MIXED"
    
    def process_article(self, article: NewsArticle) -> NewsArticle:
        """Process article with all analysis"""
        article.importance_score = self.calculate_importance_score(article)
        article.fact_speculation_analysis = self.analyze_content(article)
        article.key_highlights = self.extract_key_highlights(article)
        
        # Truncate summary if needed
        max_length = self.config.config.get("report", {}).get("max_summary_length", 300)
        if len(article.summary) > max_length:
            article.summary = article.summary[:max_length] + "..."
        
        # Clean HTML from summary
        article.summary = re.sub('<[^<]+?>', '', article.summary)
        
        return article

class EmailReporter:
    """ email reporter with better formatting and email delivery"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.credential_manager = SecureCredentialManager()
    
    def generate__report(self, articles: List[NewsArticle]) -> str:
        """Generate  HTML report with improved layout"""
        # Group articles by category and importance
        categorized = {}
        high_importance = []
        duplicate_groups = {}
        
        for article in articles:
            # Group by category
            if article.category not in categorized:
                categorized[article.category] = []
            categorized[article.category].append(article)
            
            # High importance articles (score > 50)
            if article.importance_score > 50:
                high_importance.append(article)
        
        # Get duplicate groups if enabled
        if self.config.config.get("report", {}).get("highlight_duplicates", True):
            db = NewsDatabase(self.config)
            duplicate_groups = db.get_duplicate_groups(24)
        
        # Generate report
        report_title = self.config.config.get("report", {}).get("title", " Personal News Digest")
        report_date = datetime.now().strftime("%A, %B %d, %Y")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{report_title}</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    text-align: center;
                }}
                .header h1 {{ margin: 0; font-size: 2.2em; }}
                .header .subtitle {{ margin-top: 10px; opacity: 0.9; }}
                
                .summary-stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #667eea; }}
                .stat-label {{ color: #666; margin-top: 5px; }}
                
                .section {{
                    background: white;
                    margin: 30px 0;
                    border-radius: 10px;
                    box-shadow: 0 2px 15px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .section-header {{
                    background: #667eea;
                    color: white;
                    padding: 20px;
                    font-size: 1.4em;
                    font-weight: bold;
                }}
                .section-content {{ padding: 20px; }}
                
                .article {{
                    margin: 20px 0;
                    padding: 20px;
                    border-left: 4px solid #ddd;
                    background: #fafafa;
                    border-radius: 0 8px 8px 0;
                    transition: all 0.3s ease;
                }}
                .article:hover {{ transform: translateX(5px); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                
                .high-importance {{ border-left-color: #e74c3c; background: #fdf2f2; }}
                .medium-importance {{ border-left-color: #f39c12; background: #fef9f3; }}
                .fact {{ border-left-color: #27ae60; }}
                .speculation {{ border-left-color: #e74c3c; }}
                .mixed {{ border-left-color: #f39c12; }}
                .neutral {{ border-left-color: #95a5a6; }}
                
                .article-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 15px;
                }}
                .article-title {{
                    font-size: 1.3em;
                    font-weight: bold;
                    margin: 0;
                }}
                .article-title a {{
                    color: #2c3e50;
                    text-decoration: none;
                }}
                .article-title a:hover {{ color: #667eea; }}
                
                .importance-badge {{
                    background: #667eea;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.8em;
                    font-weight: bold;
                    white-space: nowrap;
                }}
                .high-importance .importance-badge {{ background: #e74c3c; }}
                .medium-importance .importance-badge {{ background: #f39c12; }}
                
                .article-meta {{
                    color: #666;
                    font-size: 0.9em;
                    margin-bottom: 10px;
                }}
                .article-summary {{ margin-bottom: 15px; }}
                
                .highlights {{
                    background: #f8f9ff;
                    border: 1px solid #e1e8ff;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 15px 0;
                }}
                .highlights-title {{
                    font-weight: bold;
                    margin-bottom: 10px;
                    color: #667eea;
                }}
                .highlight-item {{
                    margin: 8px 0;
                    padding: 8px 0;
                    border-bottom: 1px solid #eee;
                }}
                .highlight-item:last-child {{ border-bottom: none; }}
                
                .duplicate-notice {{
                    background: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 6px;
                    padding: 10px;
                    margin: 10px 0;
                    font-size: 0.9em;
                }}
                
                .analysis-tag {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 12px;
                    font-size: 0.8em;
                    font-weight: bold;
                    margin-right: 10px;
                }}
                .factual {{ background: #d4edda; color: #155724; }}
                .speculation {{ background: #f8d7da; color: #721c24; }}
                .mixed {{ background: #fff3cd; color: #856404; }}
                .neutral {{ background: #e2e3e5; color: #383d41; }}
                
                .footer {{
                    text-align: center;
                    padding: 30px;
                    color: #666;
                    border-top: 1px solid #eee;
                    margin-top: 40px;
                }}
                
                @media (max-width: 768px) {{
                    body {{ padding: 10px; }}
                    .header {{ padding: 20px; }}
                    .article-header {{ flex-direction: column; align-items: flex-start; }}
                    .importance-badge {{ margin-top: 10px; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{report_title}</h1>
                <div class="subtitle">{report_date}</div>
            </div>
            
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-number">{len(articles)}</div>
                    <div class="stat-label">Total Articles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(high_importance)}</div>
                    <div class="stat-label">High Priority</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(categorized)}</div>
                    <div class="stat-label">Categories</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(duplicate_groups)}</div>
                    <div class="stat-label">Breaking Stories</div>
                </div>
            </div>
        """
        
        # High importance articles section
        if high_importance:
            html_content += """
            <div class="section">
                <div class="section-header">🚨 High Priority News</div>
                <div class="section-content">
            """
            
            for article in sorted(high_importance, key=lambda x: x.importance_score, reverse=True)[:10]:
                html_content += self._format_article(article, is_priority=True)
            
            html_content += "</div></div>"
        
        # Breaking stories (duplicate groups)
        if duplicate_groups:
            html_content += """
            <div class="section">
                <div class="section-header">📈 Breaking Stories (Multiple Sources)</div>
                <div class="section-content">
            """
            
            for group_id, group_articles in duplicate_groups.items():
                if len(group_articles) > 1:
                    # Sort by importance and take the best one
                    primary_article = max(group_articles, key=lambda x: x.importance_score)
                    other_sources = [a.source for a in group_articles if a != primary_article]
                    
                    html_content += f"""
                    <div class="duplicate-notice">
                        <strong>📊 Covered by {len(group_articles)} sources:</strong> 
                        {', '.join(set(other_sources))}
                    </div>
                    """
                    html_content += self._format_article(primary_article, is_breaking=True)
            
            html_content += "</div></div>"
        
        # Articles by category
        for category, cat_articles in categorized.items():
            if not cat_articles:
                continue
            
            # Sort by importance
            cat_articles.sort(key=lambda x: x.importance_score, reverse=True)
            max_articles = self.config.config.get("report", {}).get("max_articles_per_category", 20)
            cat_articles = cat_articles[:max_articles]
            
            category_name = category.title().replace('_', ' ')
            html_content += f"""
            <div class="section">
                <div class="section-header">📰 {category_name} ({len(cat_articles)} articles)</div>
                <div class="section-content">
            """
            
            for article in cat_articles:
                html_content += self._format_article(article)
            
            html_content += "</div></div>"
        
        # Footer
        html_content += f"""
            <div class="footer">
                <p>Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}</p>
                <p>Personal AI News Aggregator v3.0 - Secure Local Processing</p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _format_article(self, article: NewsArticle, is_priority: bool = False, is_breaking: bool = False) -> str:
        """Format individual article HTML"""
        # Determine importance class
        importance_class = ""
        importance_label = ""
        
        if article.importance_score > 75:
            importance_class = "high-importance"
            importance_label = "HIGH"
        elif article.importance_score > 40:
            importance_class = "medium-importance"
            importance_label = "MEDIUM"
        else:
            importance_label = "NORMAL"
        
        # Analysis class
        analysis_class = article.fact_speculation_analysis.lower()
        
        # Format published time
        time_ago = self._time_ago(article.published)
        
        html = f"""
        <div class="article {importance_class} {analysis_class}">
            <div class="article-header">
                <h3 class="article-title">
                    <a href="{article.url}" target="_blank">{article.title}</a>
                </h3>
                <span class="importance-badge">{importance_label} ({article.importance_score})</span>
            </div>
            
            <div class="article-meta">
                <strong>Source:</strong> {article.source} | 
                <strong>Published:</strong> {time_ago} |
                <span class="analysis-tag {analysis_class}">{article.fact_speculation_analysis}</span>
        """
        
        if article.author:
            html += f" | <strong>Author:</strong> {article.author}"
        
        html += "</div>"
        
        # Article summary
        if article.summary:
            html += f'<div class="article-summary">{article.summary}</div>'
        
        # Key highlights
        if article.key_highlights:
            html += """
            <div class="highlights">
                <div class="highlights-title">🔍 Key Highlights:</div>
            """
            for highlight in article.key_highlights:
                html += f'<div class="highlight-item">• {highlight}</div>'
            html += "</div>"
        
        # Full content preview if available
        if article.full_content and self.config.config.get("report", {}).get("show_full_content", False):
            preview = article.full_content[:500] + "..." if len(article.full_content) > 500 else article.full_content
            html += f'<div class="full-content-preview"><strong>Preview:</strong> {preview}</div>'
        
        html += "</div>"
        return html
    
    def _time_ago(self, published: datetime) -> str:
        """Format time ago string"""
        now = datetime.now()
        diff = now - published
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    def send_email(self, content: str, recipient: str = None) -> bool:
        """Send email report securely"""
        if not self.config.config.get("email", {}).get("enabled", False):
            logging.info("Email sending disabled in configuration")
            return False
        
        credentials = self.credential_manager.get_email_credentials()
        if not credentials:
            logging.error("No email credentials found. Please configure email first.")
            return False
        
        if not recipient:
            recipient = self.config.config.get("email", {}).get("recipient", "")
            if not recipient:
                logging.error("No recipient email configured")
                return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            
            subject_template = self.config.config.get("email", {}).get("subject_template", "Daily News Digest - {date}")
            subject = subject_template.format(date=datetime.now().strftime('%Y-%m-%d'))
            
            msg['Subject'] = subject
            msg['From'] = formataddr(("Personal News Aggregator", credentials['email']))
            msg['To'] = recipient
            
            # Attach HTML content
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Create secure SSL context
            context = ssl.create_default_context()
            
            # Send email
            with smtplib.SMTP(credentials['smtp_server'], credentials['smtp_port']) as server:
                server.starttls(context=context)
                server.login(credentials['email'], credentials['password'])
                server.send_message(msg)
            
            logging.info(f"Email report sent successfully to {recipient}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
    
    def save_report(self, content: str, filename: str = None):
        """Save report to file"""
        if not filename:
            pattern = self.config.config.get("report", {}).get("filename_pattern", "news_report_{date}.html")
            filename = pattern.format(date=datetime.now().strftime('%Y%m%d_%H%M'))
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"Report saved to {filename}")
        except Exception as e:
            logging.error(f"Failed to save report: {e}")

class NewsScheduler:
    """Handle scheduling of news collection and reporting"""
    
    def __init__(self, aggregator):
        self.aggregator = aggregator
        self.config = aggregator.config
        self.setup_schedule()
    
    def setup_schedule(self):
        """Setup collection and reporting schedule"""
        if not self.config.config.get("scheduling", {}).get("enabled", False):
            return
        
        # Schedule collection times
        collection_times = self.config.config.get("scheduling", {}).get("collection_times", ["08:00", "18:00"])
        for time_str in collection_times:
            schedule.every().day.at(time_str).do(self.aggregator.run_collection)
            logging.info(f"Scheduled news collection at {time_str}")
        
        # Schedule report time
        report_time = self.config.config.get("scheduling", {}).get("report_time", "08:30")
        schedule.every().day.at(report_time).do(self.aggregator.run_report)
        logging.info(f"Scheduled news report at {report_time}")
    
    def run_scheduler(self):
        """Run the scheduler loop"""
        logging.info("News scheduler started. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logging.info("Scheduler stopped by user")

class NewsAggregator:
    """main orchestrator class"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = ConfigManager(config_path)
        self.db = NewsDatabase(self.config)
        self.collector = NewsCollector(self.config)
        self.analyzer = Analyzer(self.config)
        self.reporter = EmailReporter(self.config)
        self.scheduler = NewsScheduler(self)
    
    def run_collection(self):
        """Run news collection and analysis"""
        logging.info("Starting  news collection...")
        
        # Clean up old articles first
        self.db.cleanup_old_articles()
        
        # Collect new articles
        articles = self.collector.collect_all_news()
        logging.info(f"Collected {len(articles)} raw articles")
        
        # Process and analyze each article
        processed = 0
        for article in articles:
            if not self.db.url_exists(article.url):
                # Analyze and enhance article
                _article = self.analyzer.process_article(article)
                
                # Save to database
                self.db.save_article(_article)
                processed += 1
        
        logging.info(f"Processed {processed} new articles")
        return processed
    
    def run_report(self):
        """Generate and optionally send report"""
        logging.info("Generating  news report...")
        
        # Get recent articles
        recent_articles = self.db.get_recent_articles(24)
        if not recent_articles:
            logging.info("No recent articles to report")
            return
        
        # Generate  report
        report_content = self.reporter.generate__report(recent_articles)
        
        # Save report
        self.reporter.save_report(report_content)
        
        # Send email if configured
        if self.config.config.get("email", {}).get("enabled", False):
            self.reporter.send_email(report_content)
        
        logging.info(" report generated successfully")
    
    def run_daily_collection(self):
        """Run complete daily collection and reporting"""
        processed = self.run_collection()
        if processed > 0:
            self.run_report()
        else:
            logging.info("No new articles processed, skipping report generation")
    
    def configure_email(self):
        """Interactive email configuration"""
        print("Email Configuration Setup")
        print("=" * 30)
        
        email = input("Enter your email address: ").strip()
        password = getpass.getpass("Enter your email password: ")
        smtp_server = input("Enter SMTP server (e.g., smtp.gmail.com): ").strip()
        smtp_port = int(input("Enter SMTP port (e.g., 587): ").strip())
        recipient = input("Enter recipient email (press Enter for same as sender): ").strip()
        
        if not recipient:
            recipient = email
        
        # Store credentials securely
        SecureCredentialManager.set_email_credentials(email, password, smtp_server, smtp_port)
        
        # Update config
        self.config.config["email"]["enabled"] = True
        self.config.config["email"]["recipient"] = recipient
        self.config.save_config(self.config.config)
        
        print("Email configuration saved securely!")
    
    def show_status(self):
        """ status display"""
        print(" Personal AI News Feed - Status")
        print("=" * 50)
        
        # Configuration status
        sources = self.config.get_enabled_sources()
        total_sources = sum(len(source_list) for source_list in sources.values())
        print(f"Enabled news sources: {total_sources}")
        
        for category, source_list in sources.items():
            print(f"\n  {category.title().replace('_', ' ')}:")
            for source in source_list:
                priority_stars = "⭐" * source.priority
                print(f"    ✅ {source.name} {priority_stars}")
                if source.note:
                    print(f"       Note: {source.note}")
        
        # Email status
        email_config = self.config.config.get("email", {})
        credentials = SecureCredentialManager.get_email_credentials()
        email_status = "✅ Configured" if credentials and email_config.get("enabled") else "❌ Not configured"
        print(f"\nEmail delivery: {email_status}")
        if email_config.get("recipient"):
            print(f"  Recipient: {email_config['recipient']}")
        
        # Scheduling status
        scheduling_config = self.config.config.get("scheduling", {})
        if scheduling_config.get("enabled"):
            print(f"\nScheduling: ✅ Enabled")
            print(f"  Collection times: {', '.join(scheduling_config.get('collection_times', []))}")
            print(f"  Report time: {scheduling_config.get('report_time', 'Not set')}")
        else:
            print(f"\nScheduling: ❌ Disabled")
        
        # Database statistics
        try:
            recent_articles = self.db.get_recent_articles(24)
            duplicate_groups = self.db.get_duplicate_groups(24)
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor = conn.execute("""
                SELECT category, COUNT(*), AVG(importance_score) 
                FROM articles 
                GROUP BY category 
                ORDER BY COUNT(*) DESC
            """)
            categories = cursor.fetchall()
            conn.close()
            
            print(f"\nDatabase Statistics:")
            print(f"  Total articles: {total_articles}")
            print(f"  Recent (24h): {len(recent_articles)}")
            print(f"  Breaking stories: {len(duplicate_groups)}")
            
            print(f"\nCategory breakdown:")
            for category, count, avg_score in categories:
                print(f"  {category}: {count} articles (avg importance: {avg_score:.1f})")
                
        except Exception as e:
            print(f"Database error: {e}")
    
    def start_scheduler(self):
        """Start the background scheduler"""
        if not self.config.config.get("scheduling", {}).get("enabled", False):
            print("Scheduling is disabled. Enable it in config.json first.")
            return
        
        self.scheduler.run_scheduler()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Personal News Aggregator v3.0")
    parser.add_argument("command", nargs="?", default="collect",
                       choices=["collect", "report", "status", "schedule", "config-email", "run-scheduler"],
                       help="Command to execute")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    
    args = parser.parse_args()
    
    try:
        aggregator = NewsAggregator(args.config)
        
        if args.command == "status":
            aggregator.show_status()
        elif args.command == "collect":
            aggregator.run_collection()
        elif args.command == "report":
            aggregator.run_report()
        elif args.command == "schedule":
            aggregator.run_daily_collection()
        elif args.command == "config-email":
            aggregator.configure_email()
        elif args.command == "run-scheduler":
            aggregator.start_scheduler()
        else:
            aggregator.run_daily_collection()
            
    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()