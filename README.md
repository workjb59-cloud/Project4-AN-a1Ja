# Aljarida Archive Scraper

Automated web scraper for extracting articles from [Aljarida newspaper archive](https://www.aljarida.com/archive) and uploading to AWS S3.

## Features

- ✅ Scrapes archive from June 2, 2007 until today
- ✅ Extracts three columns: **القسم** (Category), **العنوان** (Title), **المحتوى** (Content)
- ✅ Saves data as Excel files (`.xlsx`)
- ✅ Partitioned storage in S3: `aljarida/year=YYYY/month=MM/day=DD/data.xlsx`
- ✅ Automated GitHub Actions workflow
- ✅ Respectful rate limiting and retry logic
- ✅ UTF-8 encoding for Arabic content

## Setup

### 1. Install Dependencies (Local Testing)

```bash
pip install -r requirements.txt
```

### 2. Configure GitHub Secrets

Go to your repository **Settings → Secrets and variables → Actions** and add these secrets:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `S3_BUCKET_NAME` | Your S3 bucket name | `my-aljarida-bucket` |

### 3. Ensure S3 Bucket Exists

Make sure your S3 bucket is created and your AWS credentials have permissions to write to it.

## Usage

### GitHub Actions (Recommended)

#### Option 1: Manual Trigger

1. Go to **Actions** tab in your repository
2. Select **"Scrape Aljarida Archive"** workflow
3. Click **"Run workflow"**
4. Optional: Specify custom date range
   - Start date: `2007-06-02` (default)
   - End date: Leave empty for today, or specify `YYYY-MM-DD`

#### Option 2: Scheduled Run

The workflow runs automatically daily at 2 AM UTC (optional, configured in `.github/workflows/scrape.yml`)

### Local Testing

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export S3_BUCKET_NAME="your_bucket_name"

# Run scraper (full archive from 2007-06-02 to today)
python scraper.py

# Run with custom date range
python scraper.py 2007-06-02 2007-06-10
```

## Output Structure

### S3 Directory Structure

```
s3://your-bucket/
└── aljarida/
    ├── year=2007/
    │   └── month=06/
    │       ├── day=02/
    │       │   └── data.xlsx
    │       ├── day=03/
    │       │   └── data.xlsx
    │       └── ...
    ├── year=2008/
    │   └── ...
    └── ...
```

### Excel File Format

Each `data.xlsx` file contains three columns:

| القسم | العنوان | المحتوى |
|------|---------|----------|
| أخبار الأولى | Article title... | Full article content... |
| محليات | Another article... | More content... |

## How It Works

1. **Archive Scraping**: Fetches article list from `https://www.aljarida.com/archive/YYYY/M/D`
2. **Pagination Handling**: Automatically detects and scrapes all pages (`?pgno=2`, `?pgno=3`, etc.)
3. **Content Extraction**: For each article, visits the article URL and extracts full content
4. **Excel Creation**: Creates Excel file with القسم, العنوان, المحتوى columns
5. **S3 Upload**: Uploads to partitioned path in S3

## Rate Limiting

- 1 second delay between articles
- 2 second delay between days
- Automatic retry with exponential backoff on failures

## Troubleshooting

### ✗ Error: "InvalidAccessKeyId - The AWS Access Key Id you provided does not exist in our records"

This error means GitHub Actions cannot access your AWS credentials. Try these steps:

#### Step 1: Verify Secret Names Match Exactly

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and ensure you have:
- `AWS_ACCESS_KEY_ID` (not aws_access_key_id or AWS_ACCESS_KEY)
- `AWS_SECRET_ACCESS_KEY` (not aws_secret_access_key)
- `S3_BUCKET_NAME` (not s3_bucket_name or BUCKET_NAME)

Secret names are **case-sensitive** and must match exactly!

#### Step 2: Check for Extra Whitespace

When adding secrets:
1. Copy the value
2. Paste into a text editor first
3. Remove any spaces or newlines at the beginning/end
4. Then paste into GitHub secrets

#### Step 3: Verify AWS Credentials Are Valid

Test your credentials locally:

```powershell
# PowerShell
$env:AWS_ACCESS_KEY_ID="your_actual_key"
$env:AWS_SECRET_ACCESS_KEY="your_actual_secret"
$env:S3_BUCKET_NAME="your_bucket"

# Test AWS connection
pip install boto3
python -c "import boto3; s3 = boto3.client('s3'); print('Buckets:', [b['Name'] for b in s3.list_buckets()['Buckets']])"
```

If this fails locally, your AWS credentials are incorrect.

#### Step 4: Check IAM Permissions

Your AWS user/role needs these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

#### Step 5: Re-create the Secrets

Sometimes secrets get corrupted. Delete and recreate them:
1. Go to **Settings → Secrets and variables → Actions**
2. Click on each secret → **Remove**
3. Add them again with **New repository secret**

### GitHub Actions Failing?

- Check that all three secrets are properly set
- Verify S3 bucket exists and credentials have write permissions
- View logs in Actions tab for detailed error messages
- Check the "Verify AWS Secrets" step in the workflow logs

### Local Testing Issues?

```bash
# Test AWS credentials
aws s3 ls s3://your-bucket-name/

# Check Python version (3.11+ recommended)
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## License

MIT License

## Notes

⚠️ **Important**: 
- The full archive (2007-2026) contains thousands of articles and will take considerable time
- Consider testing with a small date range first
- Respect the website's terms of service
- This scraper implements polite rate limiting