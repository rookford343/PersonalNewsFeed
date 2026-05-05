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
    
    def generate_enhanced_report(self, articles: List[NewsArticle]) -> str:
        """Generate enhanced HTML report with working navigation and proper category ordering"""
        
        # Define category configuration with your preferred order and consolidated sections
        category_config = {
            'critical_alerts': {
                'title': '🚨 Critical News & Alerts',
                'color': '#e74c3c',
                'priority': 1,
                'description': 'Breaking news, security alerts, and high-priority updates',
                'source_categories': ['government_alerts', 'breaking_news']
            },
            'world': {
                'title': '🌍 World News',
                'color': '#34495e',
                'priority': 2,
                'description': 'International developments and global security context',
                'source_categories': ['world_news', 'world']
            },
            'united_states': {
                'title': '🇺🇸 United States News',
                'color': '#16a085',
                'priority': 3,
                'description': 'National politics, policy, and domestic developments',
                'source_categories': ['united_states', 'usa', 'national']
            },
            'local': {
                'title': '📍 Local & Regional News',
                'color': '#95a5a6',
                'priority': 4,
                'description': 'Indianapolis area, Indiana, and Midwest regional news',
                'source_categories': ['local_midwest', 'local', 'indiana', 'midwest']
            },
            'cybersecurity': {
                'title': '🔒 Cybersecurity & Threat Intelligence',
                'color': '#c0392b',
                'priority': 5,
                'description': 'Security alerts, vulnerabilities, threat analysis, and incident response',
                'source_categories': ['cybersecurity', 'threat_intelligence', 'security']
            },
            'technology': {
                'title': '💻 Technology & Innovation',
                'color': '#3498db',
                'priority': 6,
                'description': 'Tech trends, innovations, and industry developments',
                'source_categories': ['technology', 'tech', 'innovation']
            },
            'electric_vehicles': {
                'title': '🔋 Electric Vehicles & Clean Energy',
                'color': '#2ecc71',
                'priority': 7,
                'description': 'EV market, charging infrastructure, and clean energy policy',
                'source_categories': ['electric_vehicles', 'clean_energy', 'ev']
            },
            'critical_infrastructure': {
                'title': '⚡ Critical Infrastructure & Power Grid',
                'color': '#f39c12',
                'priority': 8,
                'description': 'Power industry, grid security, and infrastructure news',
                'source_categories': ['critical_infrastructure', 'power_grid', 'infrastructure']
            }
        }
        
        # Consolidate articles into the new category structure
        consolidated_categories = {}
        
        for article in articles:
            # Find which consolidated category this article belongs to
            assigned_category = None
            
            # Check if it's a critical alert first
            if (article.importance_score > 75 and 
                article.category in ['cybersecurity', 'critical_infrastructure', 'government_alerts']):
                assigned_category = 'critical_alerts'
            else:
                # Find matching category based on source categories
                for cat_key, cat_config in category_config.items():
                    if article.category in cat_config['source_categories']:
                        assigned_category = cat_key
                        break
                
                # Fallback - try partial matching
                if not assigned_category:
                    article_cat_lower = article.category.lower()
                    for cat_key, cat_config in category_config.items():
                        for source_cat in cat_config['source_categories']:
                            if source_cat in article_cat_lower or article_cat_lower in source_cat:
                                assigned_category = cat_key
                                break
                        if assigned_category:
                            break
            
            # Default category if no match found
            if not assigned_category:
                if 'cyber' in article.category.lower() or 'security' in article.category.lower():
                    assigned_category = 'cybersecurity'
                elif 'local' in article.category.lower() or 'midwest' in article.category.lower():
                    assigned_category = 'local'
                else:
                    assigned_category = 'technology'  # Default fallback
            
            if assigned_category not in consolidated_categories:
                consolidated_categories[assigned_category] = []
            consolidated_categories[assigned_category].append(article)
        
        # Calculate statistics
        total_articles = len(articles)
        high_importance = [a for a in articles if a.importance_score > 50]
        critical_alerts = [a for a in articles if a.importance_score > 75]
        categories_with_content = len([cat for cat in consolidated_categories if consolidated_categories[cat]])
        
        # Sort categories by priority and filter out empty ones
        sorted_categories = []
        for cat_key in sorted(category_config.keys(), key=lambda x: category_config[x]['priority']):
            if cat_key in consolidated_categories and consolidated_categories[cat_key]:
                sorted_categories.append((cat_key, consolidated_categories[cat_key]))
        
        # Generate navigation menu
        nav_items = []
        for category, cat_articles in sorted_categories:
            config = category_config[category]
            nav_items.append(f'<a href="#{category}" class="nav-link">{config["title"]} ({len(cat_articles)})</a>')
        
        report_date = datetime.now().strftime("%A, %B %d, %Y")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Personal News Feed</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    background: #f8f9fa;
                    color: #333;
                }}
                
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    min-height: 100vh;
                }}
                
                .header {{ 
                    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                    color: white;
                    padding: 2rem;
                    text-align: center;
                    position: sticky;
                    top: 0;
                    z-index: 1000;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                
                .header h1 {{ 
                    font-size: 2.5em; 
                    font-weight: 300; 
                    margin-bottom: 0.5rem;
                }}
                
                .header .subtitle {{ 
                    font-size: 1.1em;
                    opacity: 0.9;
                    margin-bottom: 1rem;
                }}
                
                .header .location {{ 
                    font-size: 0.9em;
                    opacity: 0.8;
                }}
                
                .navigation {{
                    background: #34495e;
                    padding: 1rem 2rem;
                    overflow-x: auto;
                    white-space: nowrap;
                    border-bottom: 1px solid #2c3e50;
                }}
                
                .nav-link {{
                    display: inline-block;
                    color: #ecf0f1;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    margin-right: 1rem;
                    border-radius: 6px;
                    font-size: 0.9em;
                    transition: all 0.3s ease;
                    cursor: pointer;
                }}
                
                .nav-link:hover {{
                    background: #3498db;
                    color: white;
                }}
                
                .dashboard {{
                    padding: 2rem;
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                }}
                
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 1.5rem;
                    margin-bottom: 2rem;
                }}
                
                .stat-card {{
                    background: white;
                    padding: 1.5rem;
                    border-radius: 12px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                    text-align: center;
                    transition: transform 0.3s ease;
                    border-left: 4px solid #3498db;
                }}
                
                .stat-card:hover {{ 
                    transform: translateY(-2px); 
                    box-shadow: 0 6px 20px rgba(0,0,0,0.15);
                }}
                
                .stat-number {{ 
                    font-size: 2.5em; 
                    font-weight: bold; 
                    margin-bottom: 0.5rem;
                    color: #2c3e50;
                }}
                
                .stat-label {{ 
                    color: #7f8c8d; 
                    font-size: 0.9em;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                
                .section {{
                    margin: 0;
                    border-bottom: 1px solid #ecf0f1;
                }}
                
                .section-header {{
                    padding: 1.5rem 2rem;
                    font-size: 1.4em;
                    font-weight: 600;
                    color: white;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                
                .section-header:hover {{
                    opacity: 0.9;
                }}
                
                .section-title {{
                    display: flex;
                    flex-direction: column;
                    gap: 0.25rem;
                }}
                
                .section-description {{
                    font-size: 0.8em;
                    opacity: 0.9;
                    font-weight: 300;
                }}
                
                .section-controls {{
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                }}
                
                .article-count {{
                    background: rgba(255,255,255,0.2);
                    padding: 0.25rem 0.75rem;
                    border-radius: 15px;
                    font-size: 0.8em;
                }}
                
                .toggle-btn {{
                    background: none;
                    border: none;
                    color: white;
                    font-size: 1.2em;
                    cursor: pointer;
                    padding: 0.25rem;
                    border-radius: 4px;
                    transition: background 0.3s ease;
                }}
                
                .toggle-btn:hover {{
                    background: rgba(255,255,255,0.1);
                }}
                
                .section-content {{ 
                    padding: 2rem;
                    background: white;
                    display: none;
                }}
                
                .section-content.expanded {{
                    display: block;
                }}
                
                .article {{
                    margin: 1.5rem 0;
                    padding: 1.5rem;
                    background: #fafafa;
                    border-radius: 12px;
                    border-left: 4px solid #ddd;
                    transition: all 0.3s ease;
                }}
                
                .article:hover {{ 
                    transform: translateX(5px); 
                    box-shadow: 0 6px 20px rgba(0,0,0,0.1); 
                    background: white;
                }}
                
                .critical-alert {{ 
                    border-left-color: #e74c3c; 
                    background: linear-gradient(135deg, #fdf2f2 0%, #fef5f5 100%);
                    box-shadow: 0 4px 15px rgba(231, 76, 60, 0.1);
                }}
                
                .high-importance {{ 
                    border-left-color: #f39c12; 
                    background: linear-gradient(135deg, #fef9f3 0%, #fffbf0 100%);
                }}
                
                .medium-importance {{ 
                    border-left-color: #3498db; 
                    background: linear-gradient(135deg, #f0f8ff 0%, #f8fbff 100%);
                }}
                
                .article-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 1rem;
                    gap: 1rem;
                }}
                
                .article-title {{
                    font-size: 1.3em;
                    font-weight: 600;
                    margin: 0;
                    flex: 1;
                }}
                
                .article-title a {{
                    color: #2c3e50;
                    text-decoration: none;
                    transition: color 0.3s ease;
                }}
                
                .article-title a:hover {{ 
                    color: #3498db; 
                }}
                
                .importance-badge {{
                    padding: 0.4rem 0.8rem;
                    border-radius: 20px;
                    font-size: 0.75em;
                    font-weight: 600;
                    white-space: nowrap;
                }}
                
                .critical-badge {{ background: #e74c3c; color: white; }}
                .high-badge {{ background: #f39c12; color: white; }}
                .medium-badge {{ background: #3498db; color: white; }}
                .normal-badge {{ background: #95a5a6; color: white; }}
                
                .article-meta {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 1rem;
                    color: #7f8c8d;
                    font-size: 0.9em;
                    margin-bottom: 1rem;
                    align-items: center;
                }}
                
                .meta-item {{
                    display: flex;
                    align-items: center;
                    gap: 0.25rem;
                }}
                
                .analysis-tag {{
                    padding: 0.25rem 0.6rem;
                    border-radius: 12px;
                    font-size: 0.75em;
                    font-weight: 500;
                }}
                
                .factual {{ background: #d4edda; color: #155724; }}
                .speculation {{ background: #f8d7da; color: #721c24; }}
                .mixed {{ background: #fff3cd; color: #856404; }}
                .neutral {{ background: #e2e3e5; color: #383d41; }}
                
                .article-summary {{ 
                    margin-bottom: 1rem;
                    color: #555;
                    line-height: 1.7;
                }}
                
                .show-more-btn {{
                    background: #3498db;
                    color: white;
                    border: none;
                    padding: 0.75rem 1.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 0.9em;
                    margin: 1rem auto;
                    display: block;
                    transition: all 0.3s ease;
                }}
                
                .show-more-btn:hover {{
                    background: #2980b9;
                    transform: translateY(-1px);
                }}
                
                .footer {{
                    background: #2c3e50;
                    color: white;
                    text-align: center;
                    padding: 2rem;
                }}
                
                .footer-links {{
                    margin-top: 1rem;
                }}
                
                .footer-links a {{
                    color: #3498db;
                    text-decoration: none;
                    margin: 0 1rem;
                }}
                
                @media (max-width: 768px) {{
                    .header {{ padding: 1rem; }}
                    .navigation {{ padding: 1rem; }}
                    .dashboard {{ padding: 1rem; }}
                    .section-content {{ padding: 1rem; }}
                    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
                    .article-header {{ flex-direction: column; align-items: flex-start; }}
                    .nav-link {{ margin-bottom: 0.5rem; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Personal News Feed</h1>
                    <div class="subtitle">{report_date}</div>
                    <div class="location">📍 Westfield, Indiana</div>
                </div>
                
                <div class="navigation">
                    {''.join(nav_items)}
                </div>
                
                <div class="dashboard">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-number">{total_articles}</div>
                            <div class="stat-label">Total Articles</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len(critical_alerts)}</div>
                            <div class="stat-label">Critical Alerts</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len(high_importance)}</div>
                            <div class="stat-label">High Priority</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{categories_with_content}</div>
                            <div class="stat-label">Categories</div>
                        </div>
                    </div>
                </div>
        """
        
        # Generate category sections in the specified order
        for category, cat_articles in sorted_categories:
            if not cat_articles:
                continue
            
            config = category_config[category]
            
            # Sort by importance
            cat_articles.sort(key=lambda x: x.importance_score, reverse=True)
            
            # Show top 3 articles by default
            top_articles = cat_articles[:3]
            remaining_articles = cat_articles[3:]
            
            html_content += f"""
            <div class="section" id="{category}">
                <div class="section-header" style="background: linear-gradient(135deg, {config['color']} 0%, {config['color']}dd 100%);" onclick="toggleSection('{category}')">
                    <div class="section-title">
                        <div>{config['title']}</div>
                        <div class="section-description">{config['description']}</div>
                    </div>
                    <div class="section-controls">
                        <div class="article-count">{len(cat_articles)} articles</div>
                        <button class="toggle-btn" id="toggle-{category}">▼</button>
                    </div>
                </div>
                <div class="section-content" id="content-{category}">
            """
            
            # Top articles
            for article in top_articles:
                html_content += self._format_enhanced_article(article)
            
            # Show more button and remaining articles
            if remaining_articles:
                html_content += f"""
                    <button class="show-more-btn" onclick="showMore('{category}')" id="showmore-{category}">
                        Show {len(remaining_articles)} more articles...
                    </button>
                    <div id="more-{category}" style="display: none;">
                """
                
                for article in remaining_articles:
                    html_content += self._format_enhanced_article(article)
                
                html_content += "</div>"
            
            html_content += "</div></div>"
        
        # Add JavaScript and footer
        html_content += f"""
                <div class="footer">
                    <div>Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')} EST</div>
                    <div style="margin-top: 0.5rem; font-size: 0.9em; opacity: 0.8;">
                        Personal News Aggregator v3.0 | Secure Local Processing
                    </div>
                    <div class="footer-links">
                        <a href="#top">Back to Top</a>
                        <a href="mailto:support@example.com">Report Issues</a>
                    </div>
                </div>
            </div>
            
            <script>
                // Toggle section visibility
                function toggleSection(sectionId) {{
                    const content = document.getElementById('content-' + sectionId);
                    const toggle = document.getElementById('toggle-' + sectionId);
                    
                    if (content.classList.contains('expanded')) {{
                        content.classList.remove('expanded');
                        toggle.textContent = '▼';
                    }} else {{
                        content.classList.add('expanded');
                        toggle.textContent = '▲';
                    }}
                }}
                
                // Show more articles in a category
                function showMore(sectionId) {{
                    const moreContent = document.getElementById('more-' + sectionId);
                    const button = document.getElementById('showmore-' + sectionId);
                    
                    if (moreContent.style.display === 'none') {{
                        moreContent.style.display = 'block';
                        button.textContent = 'Show fewer articles';
                    }} else {{
                        moreContent.style.display = 'none';
                        const count = moreContent.children.length;
                        button.textContent = `Show ${{count}} more articles...`;
                    }}
                }}
                
                // Fixed navigation - smooth scrolling for navigation links
                document.addEventListener('DOMContentLoaded', function() {{
                    document.querySelectorAll('.nav-link').forEach(link => {{
                        link.addEventListener('click', function(e) {{
                            e.preventDefault();
                            const href = this.getAttribute('href');
                            if (href && href.startsWith('#')) {{
                                const targetId = href.substring(1);
                                const target = document.getElementById(targetId);
                                
                                if (target) {{
                                    // Expand the section if it's not already expanded
                                    const content = document.getElementById('content-' + targetId);
                                    if (content && !content.classList.contains('expanded')) {{
                                        toggleSection(targetId);
                                    }}
                                    
                                    // Smooth scroll to section with offset for fixed header
                                    setTimeout(() => {{
                                        const headerHeight = document.querySelector('.header').offsetHeight;
                                        const targetPosition = target.offsetTop - headerHeight - 20;
                                        window.scrollTo({{
                                            top: targetPosition,
                                            behavior: 'smooth'
                                        }});
                                    }}, 100);
                                }}
                            }}
                        }});
                    }});
                    
                    // Auto-expand high-priority sections
                    const prioritySections = ['critical_alerts', 'cybersecurity'];
                    prioritySections.forEach(sectionId => {{
                        const element = document.getElementById(sectionId);
                        if (element) {{
                            toggleSection(sectionId);
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        return html_content
    
    def _format_enhanced_article(self, article: NewsArticle, is_critical: bool = False, is_breaking: bool = False) -> str:
        """Format individual article with clean styling"""
        # Determine styling
        article_classes = ["article"]
        badge_class = "normal-badge"
        badge_text = "NORMAL"
        
        if is_critical or article.importance_score > 75:
            article_classes.append("critical-alert")
            badge_class = "critical-badge"
            badge_text = "CRITICAL"
        elif article.importance_score > 50:
            article_classes.append("high-importance")
            badge_class = "high-badge"
            badge_text = "HIGH"
        elif article.importance_score > 25:
            article_classes.append("medium-importance")
            badge_class = "medium-badge"
            badge_text = "MEDIUM"
        
        analysis_class = article.fact_speculation_analysis.lower()
        time_ago = self._time_ago(article.published)
        
        html = f"""
        <div class="{' '.join(article_classes)}">
            <div class="article-header">
                <h3 class="article-title">
                    <a href="{article.url}" target="_blank" rel="noopener noreferrer">
                        {article.title}
                    </a>
                </h3>
                <span class="importance-badge {badge_class}">
                    {badge_text}
                </span>
            </div>
            
            <div class="article-meta">
                <div class="meta-item">
                    <span>🏢</span>
                    <strong>{article.source}</strong>
                </div>
                <div class="meta-item">
                    <span>⏰</span>
                    {time_ago}
                </div>
                <div class="analysis-tag {analysis_class}">
                    {article.fact_speculation_analysis}
                </div>
            </div>
            
            <div class="article-summary">{article.summary}</div>
        </div>
        """
        
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
        report_content = self.reporter.generate_enhanced_report(recent_articles)
        
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