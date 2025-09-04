#!/usr/bin/env python3
"""
Personal AI News Feed - Installation and Setup Script
This script helps set up the news feed system with proper configuration
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def install_dependencies():
    """Install Python dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    except FileNotFoundError:
        print("❌ requirements.txt not found")
        return False

def create_config_file():
    """Create or update config.json file"""
    print("\n⚙️  Setting up configuration...")
    
    config_exists = os.path.exists("config.json")
    if config_exists:
        response = input("config.json already exists. Overwrite? (y/n): ").lower()
        if response != 'y':
            print("Keeping existing configuration")
            return True
    
    # Default configuration
    config = {
        "database": {
            "path": "news_feed.db",
            "cleanup_days": 30
        },
        "collection": {
            "article_age_limit_days": 2,
            "request_timeout": 30,
            "rate_limit_delay": 1
        },
        "analysis": {
            "fact_keywords": [
                "announced", "confirmed", "disclosed", "reported earnings",
                "filed", "released", "published", "data shows", "statistics",
                "according to", "statement", "press release"
            ],
            "speculation_keywords": [
                "allegedly", "reportedly", "sources say", "rumors", "speculation",
                "could", "might", "may", "possible", "potential", "unconfirmed",
                "according to sources", "insider claims"
            ]
        },
        "news_sources": {
            "cybersecurity": [
                {
                    "name": "Krebs on Security",
                    "url": "https://krebsonsecurity.com/feed/",
                    "enabled": True
                },
                {
                    "name": "Dark Reading",
                    "url": "https://www.darkreading.com/rss.xml",
                    "enabled": True
                },
                {
                    "name": "BleepingComputer",
                    "url": "https://www.bleepingcomputer.com/feed/",
                    "enabled": True
                },
                {
                    "name": "ESET Blog",
                    "url": "https://feeds.feedburner.com/eset/blog",
                    "enabled": True
                }
            ],
            "technology": [
                {
                    "name": "Ars Technica",
                    "url": "https://feeds.arstechnica.com/arstechnica/index",
                    "enabled": True
                },
                {
                    "name": "WIRED",
                    "url": "https://www.wired.com/feed/rss",
                    "enabled": True
                },
                {
                    "name": "TechCrunch",
                    "url": "https://techcrunch.com/feed/",
                    "enabled": True
                }
            ],
            "electric_vehicles": [
                {
                    "name": "Electrek",
                    "url": "https://electrek.co/feed/",
                    "enabled": True
                }
            ],
            "world": [
                {
                    "name": "CNN World",
                    "url": "https://rss.cnn.com/rss/edition.rss",
                    "enabled": True
                },
                {
                    "name": "BBC World",
                    "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
                    "enabled": True
                }
            ],
            "united_states": [
                {
                    "name": "NPR News",
                    "url": "https://feeds.npr.org/1001/rss.xml",
                    "enabled": True
                },
                {
                    "name": "CNN US",
                    "url": "https://rss.cnn.com/rss/cnn_us.rss",
                    "enabled": True
                }
            ],
            "local": [
                {
                    "name": "WTHR Indianapolis",
                    "url": "https://www.wthr.com/rss/headlines",
                    "enabled": True
                },
                {
                    "name": "FOX59 Indianapolis",
                    "url": "https://fox59.com/feed/",
                    "enabled": True
                }
            ]
        },
        "report": {
            "filename_pattern": "news_report_{date}.html",
            "title": "Personal News Digest",
            "max_summary_length": 200
        }
    }
    
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("✅ Configuration file created")
        return True
    except Exception as e:
        print(f"❌ Failed to create config file: {e}")
        return False

def customize_local_news():
    """Help user customize local news sources"""
    print("\n🗞️  Local News Setup")
    print("Current local sources are set for Indianapolis area.")
    
    customize = input("Would you like to customize local news sources? (y/n): ").lower()
    if customize != 'y':
        return True
    
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        
        print("\nEnter local news sources (press Enter with empty URL to finish):")
        local_sources = []
        
        while True:
            name = input("News source name (or Enter to finish): ").strip()
            if not name:
                break
            
            url = input(f"RSS URL for {name}: ").strip()
            if not url:
                break
            
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            local_sources.append({
                "name": name,
                "url": url,
                "enabled": True
            })
            
            print(f"✅ Added {name}")
        
        if local_sources:
            config["news_sources"]["local"] = local_sources
            
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            print(f"✅ Updated config with {len(local_sources)} local sources")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to customize local sources: {e}")
        return False

def set_file_permissions():
    """Set appropriate file permissions for security"""
    if os.name == 'posix':  # Unix-like systems
        try:
            # Make scripts executable
            os.chmod("news_feed.py", 0o755)
            if os.path.exists("cleanup_database.py"):
                os.chmod("cleanup_database.py", 0o755)
            
            # Restrict access to config and future database files
            os.chmod("config.json", 0o600)
            
            print("✅ File permissions set")
            return True
        except Exception as e:
            print(f"⚠️  Could not set file permissions: {e}")
            return True  # Not critical
    else:
        print("ℹ️  File permissions (Windows system)")
        return True

def run_initial_test():
    """Run a quick test to verify setup"""
    print("\n🧪 Running initial test...")
    
    try:
        # Import and test basic functionality
        sys.path.insert(0, '.')
        from news_feed import NewsAggregator
        
        aggregator = NewsAggregator()
        aggregator.show_status()
        
        print("\n✅ Setup test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Setup test failed: {e}")
        return False

def create_shortcuts():
    """Create convenient command shortcuts"""
    print("\n🔗 Creating convenience scripts...")
    
    # Create run script
    run_script = """#!/bin/bash
# Personal AI News Feed - Run Script
cd "$(dirname "$0")"
python3 news_feed.py "$@"
"""
    
    try:
        with open("run_news_feed.sh", "w") as f:
            f.write(run_script)
        
        if os.name == 'posix':
            os.chmod("run_news_feed.sh", 0o755)
        
        print("✅ Created run_news_feed.sh")
        
        # Create Windows batch file
        batch_script = """@echo off
cd /d "%~dp0"
python news_feed.py %*
"""
        with open("run_news_feed.bat", "w") as f:
            f.write(batch_script)
        
        print("✅ Created run_news_feed.bat")
        return True
        
    except Exception as e:
        print(f"⚠️  Could not create shortcuts: {e}")
        return True  # Not critical

def main():
    """Main installation process"""
    print("Personal AI News Feed - Installation Script")
    print("=" * 50)
    
    # Check system requirements
    if not check_python_version():
        return False
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    # Create configuration
    if not create_config_file():
        return False
    
    # Customize local news
    customize_local_news()
    
    # Set file permissions
    set_file_permissions()
    
    # Create convenience scripts
    create_shortcuts()
    
    # Run test
    if not run_initial_test():
        print("\n⚠️  Setup completed with warnings. Check the error messages above.")
        return False
    
    # Success message
    print("\n" + "=" * 50)
    print("🎉 INSTALLATION COMPLETE!")
    print("=" * 50)
    
    print("\nNext steps:")
    print("1. Review and customize config.json if needed")
    print("2. Run your first collection: python news_feed.py")
    print("3. Check status anytime: python news_feed.py status")
    print("4. Set up daily automation (cron job or scheduled task)")
    
    print("\nFiles created:")
    print("• config.json - Main configuration file")
    print("• news_feed.db - Will be created on first run")
    print("• news_feed.log - Activity log")
    print("• news_report_YYYYMMDD.html - Daily reports")
    
    print("\nFor help: python news_feed.py --help")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)