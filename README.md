# logo-scraper

Tool to download company logos. Tries 3 sources in order: logo.dev API, company website, and LinkedIn.

**This project was a proof-of-concept developed in professional context. The original code was translated to English and adapted to remove sensitive informations.**

The use case for this project stemmed from a friction point in our platform's onboarding flow: whenever a new company or deal was registered, analysts were required to (i) manually download the company's logo and (ii) re-upload it into the platform. This created unnecessary friction and prevented logo standardization across records. The goal of this POC was to demonstrate that this collection process could be easily automated, improving the overall user experience. For the production version, the LinkedIn scraping step was replaced by a Google Images lookup for compliance reasons.

## Setup

```bash
git clone https://github.com/your-username/logo-scraper.git
cd logo-scraper
pip install -r requirements.txt
cp .env.example .env
# add your logo.dev API key to .env (free)
```

## Usage

```bash
# Single company
python run.py --name "Stripe"
python run.py --name "Nubank" --url "https://nubank.com.br"

# Batch
python run.py --from-file companies.json --output ./output
```

## Tests

```bash
pytest
```

## Project structure

```
logo-scraper/
├── run.py                        # Entry point — parses arguments and starts the pipeline
├── requirements.txt              # Project dependencies
├── examples/
│   └── companies.json            # Example batch input file
├── logo_scraper/
│   ├── cli.py                    # CLI argument definitions
│   ├── orchestrator.py           # Coordinates the scraping pipeline across sources
│   ├── utils.py                  # Shared helpers (file saving, URL handling, etc.)
│   └── scraper/
│       ├── logodev.py            # Fetches logos via the logo.dev API
│       ├── website.py            # Extracts logos directly from company websites
│       └── linkedin.py           # Scrapes logos from LinkedIn company pages
└── tests/
    ├── test_cli.py               # Tests for CLI argument parsing
    ├── test_logodev.py           # Tests for the logo.dev scraper
    ├── test_website.py           # Tests for the website scraper
    └── test_linkedin.py          # Tests for the LinkedIn scraper
```
