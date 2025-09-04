#!/usr/bin/env python3
"""
Code Version Checker - Verify which version of the news aggregator you're running
"""

import ast
import sys
from pathlib import Path

def check_code_version(file_path: str = "news_feed.py"):
    """Check what version of the code is being used"""
    
    if not Path(file_path).exists():
        print(f"❌ File {file_path} not found")
        print("   Please save the updated code as 'news_feed.py'")
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        print(f"Analyzing {file_path}...")
        print("=" * 40)
        
        # Check for old class names (should NOT be present)
        old_classes = [
            "EnhancedNewsDatabase",
            "EnhancedNewsCollector", 
            "EnhancedAnalyzer",
            "EnhancedEmailReporter",
            "EnhancedNewsAggregator"
        ]
        
        # Check for new class names (should be present)
        new_classes = [
            "NewsDatabase",
            "NewsCollector",
            "TextAnalyzer", 
            "EmailReporter",
            "NewsAggregator"
        ]
        
        old_found = []
        new_found = []
        
        for old_class in old_classes:
            if f"class {old_class}" in content:
                old_found.append(old_class)
        
        for new_class in new_classes:
            if f"class {new_class}" in content:
                new_found.append(new_class)
        
        # Check for proper database migration code
        has_migration = "ALTER TABLE articles ADD COLUMN" in content
        
        # Check docstring version
        version_info = "NOT FOUND"
        lines = content.split('\n')
        for line in lines[:10]:
            if "Personal News Feed - v" in line:
                version_info = line.strip('"""').strip()
                break
            elif "Enhanced Personal News Feed" in line:
                version_info = line.strip('"""').strip() + " (OLD VERSION)"
                break
        
        print(f"Version: {version_info}")
        print(f"Database migration code: {'✅ Present' if has_migration else '❌ Missing'}")
        
        if old_found:
            print(f"\n❌ OLD class names found (should be updated):")
            for class_name in old_found:
                print(f"   - {class_name}")
        
        if new_found:
            print(f"\n✅ NEW class names found:")
            for class_name in new_found:
                print(f"   - {class_name}")
        
        # Determine version status
        if old_found and not new_found:
            print(f"\n🔴 STATUS: You're running the OLD version")
            print("   Please update your news_feed.py with the new code!")
            return False
        elif new_found and not old_found and has_migration:
            print(f"\n🟢 STATUS: You're running the UPDATED version")
            return True
        elif old_found and new_found:
            print(f"\n🟡 STATUS: MIXED version (partial update)")
            print("   Please replace the entire file with the new code")
            return False
        else:
            print(f"\n🔴 STATUS: Unknown version")
            return False
            
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        return False

def check_main_function():
    """Check if the main function calls the right classes"""
    
    file_path = "news_feed.py"
    if not Path(file_path).exists():
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Look for the main function
        if "aggregator = NewsAggregator(args.config)" in content:
            print("✅ Main function uses correct class name")
            return True
        elif "aggregator = EnhancedNewsAggregator(args.config)" in content:
            print("❌ Main function uses old class name")
            return False
        else:
            print("⚠️  Could not find main function aggregator instantiation")
            return False
            
    except Exception as e:
        print(f"Error checking main function: {e}")
        return False

def main():
    """Main checker function"""
    
    print("Personal News Aggregator - Code Version Checker")
    print("=" * 50)
    
    # Check if file exists
    file_path = "news_feed.py"
    if not Path(file_path).exists():
        print(f"\n❌ {file_path} not found!")
        print("\nPlease save the updated code as 'news_feed.py'")
        print("The file should start with:")
        print('"""')
        print("Personal News Feed - v3.0")
        print("Secure news aggregation with email delivery, improved analysis, and scheduling")  
        print('"""')
        return
    
    # Check version
    is_updated = check_code_version(file_path)
    
    print("\n" + "=" * 40)
    
    # Check main function
    main_ok = check_main_function()
    
    print("\n" + "=" * 40)
    
    if is_updated and main_ok:
        print("\n🎉 Your code is READY!")
        print("\nNext steps:")
        print("1. Run: python migrate_database.py")
        print("2. Run: python news_feed.py status")
    else:
        print("\n⚠️  Action needed:")
        print("1. Save the updated code as 'news_feed.py'")
        print("2. Run this checker again")
        print("3. Then run the database migration")

if __name__ == "__main__":
    main()