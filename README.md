# Personal News Aggregator v3.0

A security-focused, privacy-first news aggregation and analysis system designed for security professionals and power grid operators. Built for local processing with enhanced HTML reporting, duplicate detection, and multi-category intelligence gathering.

## 🔒 Security-First Design

- **Complete Local Processing**: No external AI services or cloud dependencies
- **Secure Credential Storage**: OS keyring integration for email credentials  
- **Privacy Protection**: Automatic cleanup of articles older than 30 days
- **Network Security**: Minimal footprint with respectful rate limiting
- **Input Sanitization**: Comprehensive error handling and data validation

## 📊 Enhanced Reporting Features

### Professional Dashboard
- **Executive Summary**: Article counts, priority breakdown, and category statistics
- **Critical Alerts Section**: Immediate attention items (score > 75) for cybersecurity and infrastructure
- **Breaking Stories**: Multi-source duplicate detection with source attribution
- **Priority Indicators**: Visual priority system with color-coded importance levels
- **Mobile-Responsive**: Professional HTML design optimized for all devices

### Intelligent Category Organization
- **🔐 Cybersecurity & Threat Intelligence**: Security alerts, vulnerabilities, threat analysis
- **⚡ Critical Infrastructure & Power Grid**: Power industry, grid security, NERC/FERC updates
- **🏛️ Government & Regulatory Alerts**: CISA, FBI IC3, ICS-CERT advisories
- **💻 Technology & Innovation**: Tech trends, industry developments
- **🚗 Electric Vehicles & Clean Energy**: EV market, charging infrastructure, policy
- **🌍 World News**: International developments with security context
- **🇺🇸 United States News**: National politics, policy, domestic developments
- **📍 Local & Midwest News**: Indianapolis area and regional updates

### Advanced Analysis Engine
- **Fact vs. Speculation Detection**: Automated content classification
- **Importance Scoring**: Multi-factor scoring (0-100+) based on keywords, source priority, recency
- **Key Highlights Extraction**: Up to 3 key points per article
- **Duplicate Detection**: Smart grouping of similar stories across sources
- **Source Priority Weighting**: 5-star system affecting article importance

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/your-repo/personal-news-feed.git
cd personal-news-feed

# Install dependencies (Python 3.11+)
pip install feedparser requests schedule keyring

# Run initial collection and generate report
python news_feed.py schedule

# View your professional dashboard
open news_report_$(date +%Y%m%d_%H%M).html
```

## 📋 Daily Workflow

1. **Morning Brief**: `python news_feed.py schedule` for overnight news
2. **Priority Review**: Check Critical Alerts and Breaking Stories sections  
3. **Category Scan**: Quick review of professional categories (Cybersecurity, Infrastructure, Government)
4. **Deep Dive**: Click through for full articles on high-importance items
5. **Situational Awareness**: Review technology, EV, and local news for context

## 🔧 Configuration

### News Sources (40+ Curated Feeds)

**Professional Priority Sources:**
- **Cybersecurity**: Krebs on Security, Dark Reading, BleepingComputer, CISA Alerts
- **Critical Infrastructure**: Power Magazine, Utility Dive, GridWise, Energy Central
- **Government/Regulatory**: NERC, FERC, ICS-CERT, FBI IC3, NIST Cybersecurity
- **Threat Intelligence**: Malware Bytes, FireEye, CrowdStrike, Recorded Future

**Personal Interest Sources:**
- **Technology**: Ars Technica, WIRED Security, IEEE Spectrum, TechCrunch
- **Electric Vehicles**: Electrek, InsideEVs, EV industry news
- **World News**: Reuters, BBC Technology (security context)
- **Local**: WTHR Indianapolis, FOX59, Chicago Tribune (Midwest regional)

### Importance Scoring System

Articles are scored 0-100+ based on multiple factors:
- **Source Priority**: 5-star system × 5 points
- **Category Boost**: Cybersecurity +15, Infrastructure +10, Government +20
- **Keywords**: Breaking news, critical, urgent, security terms (+20 each)
- **Recency**: <6 hours (+15), 6-12 hours (+10), fresh content bonus
- **Content Quality**: Longer, detailed articles receive slight boost

### Email Configuration

```bash
# Secure email setup (uses OS keyring)
python news_feed.py config-email

# Configuration stored securely, never in plaintext files
# Supports Gmail, Outlook, corporate SMTP servers
```

## 📅 Scheduling Options

### Built-in Scheduler
```bash
# Background daemon mode
python news_feed.py run-scheduler
```

### System Integration
```bash
# Linux/macOS Cron (recommended for servers)
0 6,18 * * * cd /path/to/news-feed && python3 news_feed.py schedule

# Windows Task Scheduler
# Create daily task running: python news_feed.py schedule
```

## 🗄️ Database & Privacy

### SQLite Schema
```sql
CREATE TABLE articles (
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Privacy Protection
- **Automatic Cleanup**: Articles >30 days automatically removed
- **Local Storage**: All data remains on your machine
- **Secure Credentials**: Never stored in plaintext
- **Audit Logging**: Complete activity logs for security review

## 🛠️ Commands Reference

```bash
# Core Operations
python news_feed.py status           # System status and statistics
python news_feed.py collect          # Collect news only
python news_feed.py report           # Generate HTML report only
python news_feed.py schedule         # Full collection + report (recommended)

# Configuration
python news_feed.py config-email     # Interactive email setup

# Scheduling
python news_feed.py run-scheduler    # Background daemon mode

# Utilities
sqlite3 news_feed.db "SELECT category, COUNT(*) FROM articles GROUP BY category;"
```

## 📈 Report Structure

### Dashboard Overview
- **Statistics Cards**: Total articles, critical alerts, high priority items, active categories
- **Priority Indicators**: Visual breakdown of article importance levels
- **Location Context**: Westfield, Indiana (Indianapolis area) for local relevance

### Critical Alerts Section (Priority 1)
- Articles scoring >75 points from cybersecurity, infrastructure, or government sources
- Immediate attention items affecting grid security or critical systems
- Visual emphasis with red styling and urgent indicators

### Breaking Stories Section
- Multi-source coverage detection using duplicate grouping algorithm
- Shows primary article with source attribution for comprehensive coverage
- Indicates developing stories with significant multi-outlet attention

### Category Sections (Priority Ordered)
1. **Cybersecurity & Threat Intelligence** - Highest professional priority
2. **Critical Infrastructure & Power Grid** - Direct operational relevance  
3. **Government & Regulatory Alerts** - Compliance and policy impacts
4. **Technology & Innovation** - Industry trends and emerging tech
5. **Electric Vehicles & Clean Energy** - Personal interest and policy context
6. **World News** - Global security context and geopolitical developments
7. **United States News** - National policy and domestic security
8. **Local & Midwest News** - Regional context and community updates

## 🔐 Security Architecture

### Threat Model Protection
- **Data Exfiltration**: All processing local, no external API calls
- **Credential Exposure**: OS keyring integration, never plaintext storage
- **Network Monitoring**: Minimal footprint, only RSS over HTTPS
- **Data Retention**: Automatic 30-day cleanup prevents long-term exposure
- **Access Control**: Single-user design, no network services exposed

### Compliance Considerations
- **NERC CIP Alignment**: Supports situational awareness requirements
- **Data Privacy**: No PII collection or external data sharing
- **Audit Trail**: Complete logging for security reviews
- **Air Gap Compatible**: Can run on isolated networks (manual RSS import)

## ⚡ Performance & Scalability

### System Requirements
- **Python**: 3.11+ (uses modern syntax and performance improvements)
- **Memory**: 256MB RAM for typical operations
- **Storage**: ~100MB for 30 days of articles + database
- **Network**: Minimal bandwidth, respects rate limiting (1 req/sec)

### Processing Metrics
- **Collection Speed**: ~40 sources in <5 minutes with rate limiting
- **Analysis Speed**: ~1000 articles processed in <30 seconds
- **Report Generation**: HTML output in <10 seconds for typical volumes
- **Database Performance**: SQLite with optimized indexes for fast queries

## 🔧 Advanced Configuration

### Custom Source Addition
```python
# Edit config.json to add new sources
"your_category": [
    {
        "name": "Your News Source",
        "url": "https://example.com/rss.xml",
        "enabled": true,
        "priority": 3,
        "note": "Industry-specific updates"
    }
]
```

### Keyword Customization
```json
{
    "analysis": {
        "importance_keywords": [
            "critical", "urgent", "security", "vulnerability", 
            "power grid", "cyber attack", "data breach"
        ],
        "fact_keywords": [
            "confirmed", "announced", "reported", "data shows",
            "according to", "official statement"
        ],
        "speculation_keywords": [
            "allegedly", "reportedly", "rumors", "sources say",
            "could", "might", "expected", "likely"
        ]
    }
}
```

### Email Template Customization
```json
{
    "email": {
        "subject_template": "🔍 Security Director's Daily Brief - {date}",
        "send_time": "06:00",
        "include_attachments": false
    }
}
```

## 🚨 Troubleshooting

### Common Issues

**No Articles Collected**
```bash
# Check source availability
curl -I https://krebsonsecurity.com/feed/

# Verify network connectivity  
python -c "import requests; print(requests.get('https://httpbin.org/ip').json())"

# Review logs
tail -f news_feed.log
```

**Email Delivery Failures**
```bash
# Test SMTP connectivity
python -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"

# Reconfigure credentials
python news_feed.py config-email
```

**Database Issues**
```bash
# Check database integrity
sqlite3 news_feed.db "PRAGMA integrity_check;"

# View recent articles
sqlite3 news_feed.db "SELECT title, published FROM articles ORDER BY published DESC LIMIT 10;"
```

### Debug Mode
```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
python news_feed.py collect

# Test individual RSS feeds
python -c "import feedparser; print(len(feedparser.parse('RSS_URL').entries))"
```

## 🔄 Migration & Backup

### Database Migration
```bash
# Automatic migration from v2.0 to v3.0
python news_feed.py status  # Triggers migration check

# Manual backup before migration
cp news_feed.db news_feed_backup_$(date +%Y%m%d).db
```

### Configuration Backup
```bash
# Backup configuration and logs
tar -czf news_aggregator_backup_$(date +%Y%m%d).tar.gz \
    config.json news_feed.db news_feed.log *.html
```

## 🛡️ Security Best Practices

### Operational Security
1. **Regular Updates**: Keep dependencies current for security patches
2. **Log Monitoring**: Review `news_feed.log` for anomalies
3. **Network Isolation**: Consider running on isolated networks for sensitive environments
4. **Access Control**: Ensure only authorized users can access report files
5. **Credential Rotation**: Periodically update email passwords

### Privacy Hardening
```bash
# Enable automatic cleanup
python -c "
import json
with open('config.json') as f: config = json.load(f)
config['database']['cleanup_days'] = 7  # More aggressive cleanup
with open('config.json', 'w') as f: json.dump(config, f, indent=2)
"
```

## 🤝 Contributing

### Development Setup
```bash
git clone https://github.com/rookford343/PersonalNewsFeed
cd PersonalNewsFeed

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Format code
black news_feed.py
```

### Security Review Process
1. All changes undergo security review for data handling
2. No external dependencies without security justification
3. Credential handling follows secure coding practices
4. Network requests limited to essential RSS feeds only

## 📞 Support & Resources

### Documentation
- **Configuration Guide**: See `config.json` comments for detailed options
- **API Reference**: All classes and methods documented with security notes
- **Security Guidelines**: Follow principle of least privilege

### Community
- **Issues**: Report bugs or request features via GitHub
- **Security**: Report vulnerabilities privately via email
- **Discussions**: Share configuration tips and custom sources

## 📜 License & Legal

**License**: Apache License 2.0 - see [LICENSE](LICENSE) file

**Compliance Notes**:
- RSS feed usage complies with robots.txt and terms of service
- No copyright content reproduction (summary/analysis only)
- Respects source rate limiting and attribution requirements
- Designed for personal/professional use, not commercial redistribution

**Security Disclaimer**: This tool is designed for personal and professional situational awareness. Users are responsible for ensuring compliance with organizational policies and applicable regulations.

---

**Version**: 3.0 (September 2025)  
**Author**: Security-focused news aggregation for power grid professionals  
**Contact**: [Your secure contact method]

*Built with security, privacy, and professional needs as primary design principles.*