import os
import subprocess
import requests
import google.generativeai as genai

def get_git_diff():
    """Gets the git diff for the current PR."""
    # The '...HEAD' syntax gets the diff between the common ancestor of the
    # main branch and the current HEAD, which is exactly what we want for a PR.
    try:
        # Assumes the default branch is 'main'. Change if yours is 'master' or other.
        diff = subprocess.run(
            ["git", "diff", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return diff.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}")
        return None

def call_gemini_api(diff, api_key):
    """Sends the diff to the Gemini LLM and returns the review."""

    # Configure the Gemini API with your key
    genai.configure(api_key=api_key)

    # Select the model. 'gemini-1.5-flash' is fast and cost-effective.
    # 'gemini-1.5-pro' is more powerful for complex reasoning.
    model = genai.GenerativeModel('gemini-1.5-flash')

    # Craft a detailed prompt. Gemini works well with a single, comprehensive prompt.
    prompt = f"""
    You are an expert senior software engineer acting as a code reviewer.
    Your task is to review the provided git diff, which contains changes for a Pull Request.

    Focus on identifying:
    - Potential bugs
    - Security vulnerabilities
    - Performance issues
    - Areas for improving code readability and maintainability

    Provide your review in a clear, bulleted list.
    If the diff is empty or contains only minor changes (like formatting or comments), respond with "No significant changes to review."

    Here is the git diff to review:
    ```diff
    {diff}
    ```
    """

    print("Sending request to Gemini API...")
    try:
        response = model.generate_content(prompt)
        # The response.text attribute contains the generated text.
        return response.text
    except Exception as e:
        # Catch potential API errors (e.g., invalid key, safety filters)
        print(f"Error calling Gemini API: {e}")
        return f"Failed to get review from Gemini. Error: {e}"

def post_pr_comment(review_body):
    """Posts the AI review as a comment on the Pull Request."""
    # GitHub provides these environment variables in the runner context
    repo = os.getenv("GITHUB_REPOSITORY")
    # GITHUB_REF_NAME is like 'refs/pull/XX/merge' for PRs
    pr_number = os.getenv("GITHUB_REF_NAME").split("/")[2]
    token = os.getenv("GITHUB_TOKEN")

    api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    payload = {
        "body": f"### 🤖 AI Code Review (Gemini)\n\n{review_body}"
    }

    print(f"Posting comment to PR #{pr_number}...")
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes
        print("Comment posted successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error posting comment to GitHub: {e}")

if __name__ == "__main__":
    # 1. Get necessary environment variables
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        exit(1)

    # 2. Get the code diff
    diff = get_git_diff()
    if not diff:
        print("No diff found. Exiting.")
        exit(0)

    # 3. Get the review from the LLM
    ai_review = call_gemini_api(diff, api_key)

    # 4. Post the review as a comment on the PR
    post_pr_comment(ai_review)