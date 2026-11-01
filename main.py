import argparse
import logging
import os
import re
import requests
import sys
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TIMEOUT = 10

# The ref paths name master, because that is the list this tool was built
# with. A repo whose default branch is main still exposes HEAD and config,
# but its logs/refs/heads/master probe normally answers 404 and counts as
# failed, not as evidence either way.
GIT_FILES = [
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

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.
    """
    parser = argparse.ArgumentParser(description="Detects publicly accessible .git directories and downloads the nine fixed .git files it checks.")
    parser.add_argument("url", help="The base URL to scan for exposed .git directory.")
    parser.add_argument("-o", "--output", help="Output directory to save downloaded files.", default="output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (DEBUG level).")
    parser.add_argument("-t", "--timeout", type=int, default=TIMEOUT, help="Timeout in seconds for each request (default: 10).")
    return parser

def looks_like_html(content):
    head = content[:512].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"<head")

def valid_head_body(content):
    """A git HEAD is a ref line or a detached 40 character hex commit id."""
    if looks_like_html(content):
        return False
    try:
        text = content.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False
    # SHA_RE only allows lower case hex. A detached HEAD written with
    # upper case letters fails this check and reads as not exposed.
    return text.startswith("ref:") or bool(SHA_RE.match(text))

def valid_git_file(file_path, content):
    """
    Per file sanity checks. A 200 alone proves nothing: catchall servers
    answer 200 with the same page for every path, and that page is not a
    git file no matter what the URL said.
    """
    if looks_like_html(content):
        return False
    if file_path == "HEAD" or file_path.startswith("refs/"):
        return valid_head_body(content)
    if file_path == "config":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return "[" in text and ("repositoryformatversion" in text or "[core]" in text or "[remote" in text)
    if file_path == "index":
        return content[:4] == b"DIRC"
    if file_path.startswith("logs/"):
        try:
            first = content.decode("utf-8", "replace").splitlines()[0]
        except IndexError:
            return False
        tokens = first.split()
        return bool(tokens) and bool(SHA_RE.match(tokens[0]))
    if file_path == "description":
        # The weakest check in the set, by necessity: a description file
        # has no fixed shape, so anything non empty and non HTML passes.
        # A catchall page in plain text would slip through this one file.
        return len(content.strip()) > 0
    return len(content) > 0

def normalize_base(url):
    """urljoin treats a final segment without a trailing slash as a file
    and replaces it, so the base is normalized to end with a slash and a
    target like /realgit keeps its own .git directory."""
    return url if url.endswith("/") else url + "/"

def check_git_access(url, timeout=TIMEOUT):
    """
    Checks if the .git directory is accessible.

    Returns:
        str: "exposed" (a 200 whose body is really a git HEAD),
        "not_exposed" (the target answered and this is not an exposed
        .git), or "unreachable" (no answer at all, so no verdict).
    """
    git_url = urljoin(normalize_base(url), ".git/HEAD")
    try:
        response = requests.get(git_url, timeout=timeout)
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not reach {git_url}: {e}")
        return "unreachable"
    if response.status_code == 200 and valid_head_body(response.content):
        logging.info(f"Found accessible .git directory at: {git_url}")
        return "exposed"
    logging.debug(f"Status code {response.status_code} for {git_url}")
    return "not_exposed"

def download_git_files(url, output_dir, timeout=TIMEOUT):
    """
    Attempts to download the nine fixed .git files, saving only bodies
    that pass the per file sanity check.

    Returns:
        tuple: (downloaded_count, failed_count)
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        logging.error(f"Failed to create directory {output_dir}: {e}")
        return 0, len(GIT_FILES)

    downloaded = 0
    failed = 0
    # HEAD is fetched again here even though check_git_access just read
    # it. I keep the two passes independent: this function must stand on
    # its own counts, not on a response cached by the check.
    for file_path in GIT_FILES:
        full_url = urljoin(normalize_base(url), f".git/{file_path}")
        output_path = os.path.join(output_dir, file_path)

        try:
            response = requests.get(full_url, timeout=timeout)
            if response.status_code != 200:
                logging.warning(f"Not downloaded: {full_url} (status {response.status_code})")
                failed += 1
                continue
            if not valid_git_file(file_path, response.content):
                logging.warning(f"Not saved: {full_url} answered 200 but the body is not a git {file_path} file")
                failed += 1
                continue

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Downloaded: {full_url} -> {output_path}")
            downloaded += 1
        except requests.exceptions.RequestException as e:
            logging.warning(f"Error downloading {full_url}: {e}")
            failed += 1
        except OSError as e:
            logging.error(f"Failed to write to file {output_path}: {e}")
            failed += 1
    return downloaded, failed

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

    state = check_git_access(url, timeout=args.timeout)
    if state == "unreachable":
        logging.error("Scan did not complete: the target could not be reached. No verdict is reported.")
        sys.exit(1)
    if state == "exposed":
        downloaded, failed = download_git_files(url, output_dir, timeout=args.timeout)
        logging.info(f"Downloaded {downloaded} of {len(GIT_FILES)} .git files to: {output_dir} ({failed} did not download)")
    else:
        logging.info(".git directory not accessible.")

if __name__ == "__main__":
    # Example Usage
    # python main.py http://example.com/ -o output_folder -v
    # python main.py https://vulnerable.website.net/
    main()
