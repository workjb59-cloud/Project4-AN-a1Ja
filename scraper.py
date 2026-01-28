import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
from datetime import datetime, timedelta
import os
import boto3
from io import BytesIO
import re
import sys


class AljaridaScraper:
    def __init__(self, aws_access_key=None, aws_secret_key=None, bucket_name=None):
        self.base_url = "https://www.aljarida.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # AWS S3 configuration
        self.bucket_name = bucket_name
        if aws_access_key and aws_secret_key:
            print(f"\nInitializing S3 client...")
            print(f"Access Key: {aws_access_key[:8]}...{aws_access_key[-4:]}")
            print(f"Secret Key: {aws_secret_key[:4]}...{aws_secret_key[-4:]}")
            print(f"Bucket: {bucket_name}")
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            
            # Test the connection
            try:
                print("\nTesting S3 connection...")
                # Try to get bucket location
                response = self.s3_client.head_bucket(Bucket=bucket_name)
                print(f"✓ Successfully connected to S3 bucket: {bucket_name}")
            except Exception as e:
                print(f"✗ Failed to connect to S3: {e}")
                print(f"\nThis means your AWS credentials are invalid or don't have access to this bucket.")
                print(f"Please check:")
                print(f"1. The AWS Access Key exists in IAM (not deleted/deactivated)")
                print(f"2. The Secret Key matches the Access Key")
                print(f"3. The IAM user has s3:PutObject permission for bucket '{bucket_name}'")
                raise
        else:
            self.s3_client = None
        
    def get_page_content(self, url, max_retries=3):
        """Fetch page content with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response.text
            except Exception as e:
                print(f"Error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
        return None
    
    def get_max_pages(self, soup):
        """Extract maximum number of pages from pagination"""
        pagination = soup.find('nav', class_='pagination')
        if not pagination:
            return 1
        
        page_links = pagination.find_all('li', class_='pager-nav')
        page_numbers = []
        
        for li in page_links:
            link = li.find('a')
            if link:
                text = link.get_text(strip=True)
                if text.isdigit():
                    page_numbers.append(int(text))
        
        return max(page_numbers) if page_numbers else 1
    
    def scrape_archive_page(self, year, month, day, page_num=1):
        """Scrape a single archive page and return list of articles"""
        if page_num == 1:
            url = f"{self.base_url}/archive/{year}/{month}/{day}"
        else:
            url = f"{self.base_url}/archive/{year}/{month}/{day}?pgno={page_num}"
        
        print(f"Scraping archive: {url}")
        
        html = self.get_page_content(url)
        if not html:
            return [], 0
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get max pages only on first page
        max_pages = self.get_max_pages(soup) if page_num == 1 else 0
        
        # Find the archive widget
        archive_widget = soup.find('div', class_='aljarida-archive-widget')
        if not archive_widget:
            print(f"No archive widget found for {year}/{month}/{day}")
            return [], max_pages
        
        # Extract articles
        articles = []
        table = archive_widget.find('table')
        if table:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    category = cells[0].get_text(strip=True)
                    link_tag = cells[1].find('a')
                    if link_tag:
                        article_url = link_tag.get('href')
                        article_title = link_tag.get('title', link_tag.get_text(strip=True))
                        articles.append({
                            'category': category,
                            'title': article_title,
                            'url': article_url
                        })
        
        print(f"Found {len(articles)} articles on page {page_num}")
        return articles, max_pages
    
    def scrape_article_content(self, article_url):
        """Scrape full article content"""
        print(f"  Fetching content: {article_url}")
        
        html = self.get_page_content(article_url)
        if not html:
            return ""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract article content
        article_content = soup.find('div', class_='articleContent')
        if article_content:
            # Remove ads and scripts
            for ad in article_content.find_all('div', class_='adInWidget'):
                ad.decompose()
            for script in article_content.find_all('script'):
                script.decompose()
            
            # Get text content and clean it
            content = article_content.get_text(separator='\n', strip=True)
            # Remove multiple newlines
            content = re.sub(r'\n{3,}', '\n\n', content)
            return content.strip()
        
        return ""
    
    def scrape_day(self, year, month, day):
        """Scrape all articles from a specific day"""
        print(f"\n{'='*60}")
        print(f"Scraping date: {year}-{month:02d}-{day:02d}")
        print(f"{'='*60}")
        
        all_articles = []
        
        # Get all article links from archive pages
        articles_list, max_pages = self.scrape_archive_page(year, month, day, 1)
        all_articles.extend(articles_list)
        
        # Scrape remaining pages if they exist
        if max_pages > 1:
            print(f"Total pages: {max_pages}")
            for page_num in range(2, max_pages + 1):
                time.sleep(1)  # Be respectful
                page_articles, _ = self.scrape_archive_page(year, month, day, page_num)
                all_articles.extend(page_articles)
        
        # Now scrape full content for each article
        articles_data = []
        for idx, article in enumerate(all_articles, 1):
            print(f"Article {idx}/{len(all_articles)}: {article['title'][:50]}...")
            time.sleep(1)  # Be respectful
            
            content = self.scrape_article_content(article['url'])
            
            articles_data.append({
                'القسم': article['category'],
                'العنوان': article['title'],
                'المحتوى': content
            })
        
        print(f"Scraped {len(articles_data)} articles")
        return articles_data
    
    def save_to_s3(self, df, year, month, day):
        """Save DataFrame to S3 as Excel file with partitioning"""
        if self.s3_client is None or self.bucket_name is None:
            print("S3 client not configured, skipping upload")
            return False
        
        # Create partitioned path
        s3_key = f"aljarida/year={year}/month={month:02d}/day={day:02d}/data.xlsx"
        
        # Convert DataFrame to Excel in memory
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Articles')
        
        excel_buffer.seek(0)
        
        try:
            print(f"Uploading to s3://{self.bucket_name}/{s3_key}...")
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=excel_buffer.getvalue(),
                ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            print(f"✓ Uploaded to S3: s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            print(f"\n✗ Error uploading to S3: {e}")
            print(f"\nDebugging info:")
            print(f"  Bucket: {self.bucket_name}")
            print(f"  Key: {s3_key}")
            print(f"  File size: {len(excel_buffer.getvalue())} bytes")
            
            # Try to get more info about the error
            if 'InvalidAccessKeyId' in str(e):
                print(f"\n⚠️  Your AWS Access Key ID is INVALID or DELETED.")
                print(f"   Go to AWS IAM Console → Users → Security Credentials")
                print(f"   and verify the access key exists and is Active.")
            elif 'SignatureDoesNotMatch' in str(e):
                print(f"\n⚠️  Your AWS Secret Access Key is INCORRECT.")
                print(f"   The secret key doesn't match the access key.")
            elif 'NoSuchBucket' in str(e):
                print(f"\n⚠️  S3 bucket '{self.bucket_name}' does not exist.")
            
            return False
    
    def scrape_and_upload(self, start_date, end_date=None):
        """Scrape archive from start_date to end_date and upload to S3"""
        if end_date is None:
            end_date = datetime.now()
        
        current_date = start_date
        total_articles = 0
        total_days = 0
        
        while current_date <= end_date:
            try:
                # Scrape the day
                articles_data = self.scrape_day(
                    current_date.year,
                    current_date.month,
                    current_date.day
                )
                
                if articles_data:
                    # Create DataFrame
                    df = pd.DataFrame(articles_data)
                    
                    # Save to S3
                    success = self.save_to_s3(
                        df,
                        current_date.year,
                        current_date.month,
                        current_date.day
                    )
                    
                    if success:
                        total_articles += len(articles_data)
                        total_days += 1
                
                # Move to next day
                current_date += timedelta(days=1)
                
                # Small delay between days
                time.sleep(2)
                
            except Exception as e:
                print(f"Error processing {current_date}: {e}")
                current_date += timedelta(days=1)
                continue
        
        print(f"\n{'='*60}")
        print(f"Scraping complete!")
        print(f"Total days processed: {total_days}")
        print(f"Total articles scraped: {total_articles}")
        print(f"{'='*60}")


if __name__ == "__main__":
    # Get AWS credentials from environment variables (set by GitHub Actions)
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    
    # Validate credentials are set
    if not AWS_ACCESS_KEY:
        print("ERROR: AWS_ACCESS_KEY_ID environment variable is not set!")
        print("Make sure GitHub secrets are configured correctly.")
        sys.exit(1)
    
    if not AWS_SECRET_KEY:
        print("ERROR: AWS_SECRET_ACCESS_KEY environment variable is not set!")
        print("Make sure GitHub secrets are configured correctly.")
        sys.exit(1)
    
    if not BUCKET_NAME:
        print("ERROR: S3_BUCKET_NAME environment variable is not set!")
        print("Make sure GitHub secrets are configured correctly.")
        sys.exit(1)
    
    # Strip any whitespace that might have been added
    AWS_ACCESS_KEY = AWS_ACCESS_KEY.strip()
    AWS_SECRET_KEY = AWS_SECRET_KEY.strip()
    BUCKET_NAME = BUCKET_NAME.strip()
    
    # Date range configuration
    START_DATE = datetime(2007, 6, 2)
    END_DATE = datetime.now()
    
    # Allow command line arguments for date range (optional)
    if len(sys.argv) >= 2:
        try:
            START_DATE = datetime.strptime(sys.argv[1], '%Y-%m-%d')
        except:
            pass
    
    if len(sys.argv) >= 3:
        try:
            END_DATE = datetime.strptime(sys.argv[2], '%Y-%m-%d')
        except:
            pass
    
    print(f"Starting scraper...")
    print(f"Date range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
    print(f"S3 Bucket: {BUCKET_NAME}")
    print(f"AWS Access Key: {AWS_ACCESS_KEY[:4]}...{AWS_ACCESS_KEY[-4:]}")
    
    # Initialize scraper
    scraper = AljaridaScraper(
        aws_access_key=AWS_ACCESS_KEY,
        aws_secret_key=AWS_SECRET_KEY,
        bucket_name=BUCKET_NAME
    )
    
    # Run scraper
    scraper.scrape_and_upload(START_DATE, END_DATE)
