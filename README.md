# Personal AI News Feed

A security-focused, privacy-first news aggregation and summarization system that runs entirely on your local machine. Built for security professionals who need quick, categorized news digests without compromising data privacy.

## Features

- **🔒 Privacy-First**: All processing done locally, no external AI services
- **📊 Fact vs. Speculation Analysis**: Automatically flags speculative content
- **📧 Executive Summary Format**: Clean, scannable reports similar to IANS style
- **🏷️ Smart Categorization**: Organizes news into predefined categories
- **🗄️ Secure Storage**: Local SQLite database with automatic cleanup
- **⚡ Fast Processing**: Designed for sub-10 minute daily review
- **🔄 Deduplication**: Prevents processing duplicate articles

## Categories

- **World News**: International events and developments
- **United States**: Domestic news and policy
- **Local News**: Regional and community updates (customizable)
- **Technology**: Tech industry news and innovations
- **Electric Vehicles**: EV market, technology, and policy
- **Cybersecurity**: Security threats, vulnerabilities, and best practices

## Quick Start

```bash
# Clone the repository
git clone https://github.com/rookford343/PersonalNewsFeed.git
cd PersonalNewsFeed

# Install dependencies
pip install -r requirements.txt

# Run the news collector
python news_feed.py

# View your report
open news_report_$(date +%Y%m%d).html
```

## Daily Usage

1. **Morning Collection**: Run `python news_feed.py` to collect overnight news
2. **Review Report**: Open the generated HTML file in your browser
3. **Quick Scan**: Color-coded articles help identify factual vs. speculative content
4. **Deep Dive**: Click article links for full stories when needed

## Security Features

### Local Processing
- No data sent to external services
- All AI analysis runs on your machine
- RSS feeds processed through secure HTTPS

### Data Privacy
- Automatic cleanup of articles older than 30 days
- Local SQLite database with encryption-ready structure
- Audit logging for all activities

### Network Security
- Minimal network footprint (RSS feeds only)
- Respectful rate limiting
- No credentials or personal data transmitted

## Configuration

### Adding News Sources

Edit the `news_sources` dictionary in `NewsCollector`:

```python
self.news_sources = {
    'cybersecurity': [
        'https://krebsonsecurity.com/feed/',
        'https://your-security-blog.com/rss.xml'
    ],
    'local': [
        'https://your-local-news.com/feed/',
        'https://city-government.gov/news/rss'
    ]
}
```

### Customizing Categories

Modify or add categories by updating the `news_sources` keys and corresponding logic.

## Scheduling

### Linux/macOS (Cron)
```bash
# Run daily at 6 AM
0 6 * * * cd /path/to/personal-ai-news-feed && /usr/bin/python3 news_feed.py
```

### Windows (Task Scheduler)
Create a daily task that runs `python news_feed.py` at your preferred time.

### Python Scheduler
Use the included scheduler option for cross-platform scheduling within the script.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  RSS Sources    │───▶│  News Collector  │───▶│  Local Database │
│  • Security     │    │  • Deduplication │    │  • SQLite       │
│  • Tech         │    │  • Rate Limiting │    │  • Auto-cleanup │
│  • World        │    │  • Error Handling│    │  • Indexing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  HTML Report    │◀───│  Text Analyzer   │◀───│  Article        │
│  • Categorized  │    │  • Fact/Spec     │    │  Processing     │
│  • Color-coded  │    │  • Summarization │    │  • Cleaning     │
│  • Time-sorted  │    │  • Local LLM*    │    │  • Validation   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Future Enhancements

### Local LLM Integration
- Replace basic analyzer with local models (Ollama, Llama.cpp)
- Enhanced summarization capabilities
- Better fact vs. speculation detection

### Advanced Features
- Email delivery automation
- Sentiment analysis
- Entity extraction (companies, people, locations)
- Trend detection across multiple days
- Mobile-friendly report formatting

## Troubleshooting

### Common Issues

**No articles collected**
- Check internet connection
- Verify RSS feed URLs are still active
- Review logs in `news_feed.log`

**Database errors**
- Ensure write permissions in project directory
- Check if multiple instances are running
- Verify SQLite installation

**Report not generating**
- Check for recent articles in database
- Verify HTML template rendering
- Review error logs

### Debug Commands

```bash
# Test RSS feed parsing
python -c "import feedparser; print(len(feedparser.parse('https://krebsonsecurity.com/feed/').entries))"

# Check database contents
sqlite3 news_feed.db "SELECT category, COUNT(*) FROM articles GROUP BY category;"

# View recent logs
tail -f news_feed.log
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security Reporting

If you discover security vulnerabilities, please report them privately via email rather than public issues.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by IANS Executive Communications format
- Built with security and privacy as primary concerns
- Designed for busy security professionals

---

**⚠️ Security Note**: This tool is designed for personal use. Ensure you comply with RSS feed terms of service and applicable laws when using automated collection tools.