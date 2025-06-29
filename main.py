import argparse
import logging
import os
import requests
import sys
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.
    """
    parser = argparse.ArgumentParser(description="Detects publicly accessible .git directories and attempts to download them.")
    parser.add_argument("url", help="The base URL to scan for exposed .git directory.")
    parser.add_argument("-o", "--output", help="Output directory to save downloaded files.", default="output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (DEBUG level).")
    return parser

def check_git_access(url):
    """
    Checks if the .git directory is accessible.

    Args:
        url (str): The base URL.

    Returns:
        bool: True if accessible, False otherwise.
    """
    git_url = urljoin(url, ".git/HEAD")  # Construct the URL to the .git/HEAD file
    try:
        response = requests.get(git_url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        if response.status_code == 200:
            logging.info(f"Found accessible .git directory at: {git_url}")
            return True
        else:
            logging.debug(f"Status code {response.status_code} for {git_url}")
            return False
    except requests.exceptions.RequestException as e:
        logging.debug(f"Error checking {git_url}: {e}")
        return False

def download_git_files(url, output_dir):
    """
    Attempts to download common .git files.

    Args:
        url (str): The base URL.
        output_dir (str): The directory to save the files to.
    """
    git_files = [
        "HEAD",
        "config",
        "description",
        "index",
        "logs/HEAD",
        "logs/refs/heads/master",
        "logs/refs/remotes/origin/HEAD",
        "refs/heads/master",
        "refs/remotes/origin/HEAD"
    ]

    try:
        os.makedirs(output_dir, exist_ok=True) # Create output directory if it doesn't exist
    except OSError as e:
        logging.error(f"Failed to create directory {output_dir}: {e}")
        return

    for file_path in git_files:
        full_url = urljoin(url, f".git/{file_path}")
        output_path = os.path.join(output_dir, file_path)

        try:
            response = requests.get(full_url)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Downloaded: {full_url} -> {output_path}")
        except requests.exceptions.RequestException as e:
            logging.debug(f"Error downloading {full_url}: {e}")
        except OSError as e:
            logging.error(f"Failed to write to file {output_path}: {e}")

def main():
    """
    Main function to run the Git repository scanner.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    url = args.url
    output_dir = args.output

    # Input validation: Check if the URL is valid (basic check)
    if not url.startswith("http://") and not url.startswith("https://"):
        logging.error("Invalid URL.  Must start with http:// or https://")
        sys.exit(1)

    logging.info(f"Scanning URL: {url}")

    if check_git_access(url):
        download_git_files(url, output_dir)
        logging.info(f"Downloaded .git files to: {output_dir}")
    else:
        logging.info(".git directory not accessible.")
        logging.info("If directory is accessible, check for common configuration errors.")

if __name__ == "__main__":
    # Example Usage
    # python main.py http://example.com/ -o output_folder -v
    # python main.py https://vulnerable.website.net/
    main()