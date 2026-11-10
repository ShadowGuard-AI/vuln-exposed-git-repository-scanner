# vuln-Exposed-Git-Repository-Scanner

I built this to answer a narrow question about a site you name: is its .git directory public, and can the fixed set of eleven .git files be downloaded? It checks .git/HEAD first and only believes a 200 when the body actually looks like a git HEAD (a ref line or a commit id), because a catchall server answers 200 with the same page for everything. Each downloaded file gets the same kind of sanity check for its own shape before it is saved.

What it does not do: it does not reconstruct a repository or a directory tree. It fetches no objects and never parses the index, so the eleven files (HEAD, config, description, index, and the log and ref files for both the main and master branch names) are evidence of exposure, not a recovered copy of the source. Earlier wording here claimed reconstruction; the code never did that, so the claim is gone.

The closing line reports how many of the eleven files actually landed, with the failures visible at the default log level. A target that cannot be reached at all exits non-zero with no verdict, which is different from a reached target with no exposed .git.

## Install
`git clone https://github.com/ShadowGuard-AI/vuln-exposed-git-repository-scanner`

## Usage
`python main.py <url> [params]`

Example: `python main.py http://127.0.0.1:8080/realgit -o output`

## Parameters
- `-h`: Show help message and exit
- `-o`: Output directory to save downloaded files (default: output).
- `-v`: Enable verbose logging.
- `-t`: Timeout in seconds for each request (default: 10).

## License
MIT License. See the LICENSE file in this repository for the full text.
