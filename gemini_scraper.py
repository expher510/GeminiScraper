import argparse
import json
import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

def download_file(url, target_path):
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with open(target_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return target_path

def sanitize_cookies(cookies):
    """Ensure cookies format matches Playwright requirements."""
    sanitized = []
    for c in cookies:
        cookie_dict = {
            "name": c.get("name"),
            "value": c.get("value"),
            "domain": c.get("domain", ".google.com"),
            "path": c.get("path", "/")
        }
        if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
            cookie_dict["sameSite"] = c["sameSite"]
        if "secure" in c:
            cookie_dict["secure"] = bool(c["secure"])
        if "httpOnly" in c:
            cookie_dict["httpOnly"] = bool(c["httpOnly"])
        sanitized.append(cookie_dict)
    return sanitized

def parse_netscape_cookies(content):
    """Parse Netscape format cookies.txt string into Playwright cookie dicts."""
    cookies = []
    lines = content.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            domain = parts[0].strip()
            path = parts[2].strip()
            secure = parts[3].strip().upper() == "TRUE"
            name = parts[5].strip()
            value = parts[6].strip()
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain if domain.startswith(".") else f".{domain}",
                "path": path,
                "secure": secure
            })
    return cookies

def load_cookies(cookies_path):
    """Load cookies from either JSON or Netscape cookies.txt file."""
    with open(cookies_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Try JSON first
    try:
        raw_cookies = json.loads(content)
        if isinstance(raw_cookies, list):
            return sanitize_cookies(raw_cookies)
    except Exception:
        pass

    # Fallback to Netscape cookies format
    return parse_netscape_cookies(content)

def main():
    parser = argparse.ArgumentParser(description="Gemini Web Automation Scraper")
    parser.add_argument("--prompt", required=True, help="Text prompt to send to Gemini")
    parser.add_argument("--image-url", help="Optional URL of an image to send")
    parser.add_argument("--cookies-file", default="cookies.txt", help="Path to cookies file (.txt or .json)")
    parser.add_argument("--output-dir", default="outputs", help="Directory to save output files and metadata")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    result_metadata_path = os.path.join(args.output_dir, "result.json")
    generated_files = []

    if not os.path.exists(args.cookies_file):
        print(f"❌ Error: Cookies file '{args.cookies_file}' not found.")
        sys.exit(1)

    cookies = load_cookies(args.cookies_file)
    if not cookies:
        print(f"❌ Error: Could not parse any valid cookies from '{args.cookies_file}'.")
        sys.exit(1)
    print(f"🔑 Successfully loaded {len(cookies)} cookies.")

    local_image_path = None
    if args.image_url:
        print(f"📥 Downloading image from: {args.image_url}")
        try:
            local_image_path = os.path.join(args.output_dir, "input_image.jpg")
            download_file(args.image_url, local_image_path)
            print("✅ Image downloaded successfully.")
        except Exception as e:
            print(f"⚠️ Failed to download image from URL: {e}")
            local_image_path = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        # Add cookies to domain
        context.add_cookies(cookies)
        page = context.new_page()

        print("🌐 Navigating to Gemini Web...")
        try:
            page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"⚠️ Initial navigation timeout/error: {e}. Retrying with commit wait...")
            page.goto("https://gemini.google.com/app", wait_until="commit", timeout=60000)
        
        time.sleep(5)

        # Check if loaded properly
        page_title = page.title()
        print(f"📄 Page Title: {page_title}")

        # Locate prompt input area
        input_selector = 'div[role="textbox"], textarea, .ql-editor, div[contenteditable="true"]'
        try:
            page.wait_for_selector(input_selector, timeout=20000)
        except Exception:
            print("❌ Could not find Gemini chat input field. Cookies might be invalid or expired.")
            page.screenshot(path=os.path.join(args.output_dir, "error_login.png"))
            browser.close()
            sys.exit(1)

        # Upload image if provided
        if local_image_path and os.path.exists(local_image_path):
            file_input = page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(local_image_path)
                print("📸 Attached image input file.")
                time.sleep(3)

        # Type prompt
        print(f"💬 Submitting prompt: {args.prompt}")
        prompt_box = page.query_selector(input_selector)
        prompt_box.click()
        prompt_box.fill(args.prompt)
        time.sleep(1)

        # Send message (click send or press Enter)
        send_btn = page.query_selector('button[aria-label*="Send"], button[aria-label*="إرسال"], button.send-button')
        if send_btn and send_btn.is_enabled():
            send_btn.click()
        else:
            prompt_box.press("Enter")
        
        print("⏳ Waiting for Gemini response...")
        time.sleep(5)

        # Wait for generation to finish (wait for stop button or wait for streaming idle)
        max_wait = 90
        start_time = time.time()
        while time.time() - start_time < max_wait:
            stop_btn = page.query_selector('button[aria-label*="Stop"], button[aria-label*="إيقاف"]')
            if not stop_btn:
                break
            time.sleep(2)

        time.sleep(3) # allow final DOM render

        # Extract latest model response
        response_elements = page.query_selector_all('model-response, .model-response-text, div[data-test-id="conversation-turn"]')
        text_response = ""
        if response_elements:
            text_response = response_elements[-1].inner_text()
        else:
            # Fallback text extraction
            text_response = page.inner_text('body')

        print("--- Gemini Response ---")
        print(text_response[:500] + ("..." if len(text_response) > 500 else ""))
        print("-----------------------")

        # Save screenshot of response
        screenshot_path = os.path.join(args.output_dir, "response_screenshot.png")
        page.screenshot(path=screenshot_path, full_page=True)
        generated_files.append("response_screenshot.png")

        # Scrape & save ONLY actual generated images inside model response
        images = page.query_selector_all('model-response img, div[data-test-id="conversation-turn"] img, .generated-image img')
        if not images:
            # Fallback if custom element wrapper is used
            images = page.query_selector_all('img[src*="blob:"], img[src*="googleusercontent"]')

        img_idx = 1
        for img in images:
            try:
                src = img.get_attribute("src") or ""

                # Evaluate natural dimensions and filter out profile avatars / small icons
                dims = page.evaluate("""(el) => {
                    return {
                        w: el.naturalWidth || el.clientWidth || 0,
                        h: el.naturalHeight || el.clientHeight || 0,
                        isAvatar: !!el.closest('button[aria-label*="Account"], header, .gb_d, [role="navigation"]')
                    };
                }""", img)

                # Skip small icons, Google account avatars (like 32x32, 96x96 "a" avatar), or header elements
                if dims.get("isAvatar") or dims.get("w", 0) < 150 or dims.get("h", 0) < 150:
                    continue

                if any(bad in src.lower() for bad in ["avatar", "favicon", "google_logo", "user_photo", "account", "/a/", "/a-/", "=s32", "=s64", "=s96", "=s128"]):
                    continue

                if src and (src.startswith("http") or src.startswith("blob:") or src.startswith("data:")):
                    img_filename = f"generated_image_{img_idx}.png"
                    img_path = os.path.join(args.output_dir, img_filename)
                    saved = False

                    # Try direct download if http URL
                    if src.startswith("http") and ("lh3.googleusercontent" in src or "generativeai" in src or "ggpht" in src):
                        try:
                            download_file(src, img_path)
                            saved = True
                            print(f"📸 Downloaded full HTTP image #{img_idx}")
                        except Exception as dl_err:
                            print(f"⚠️ Direct download failed: {dl_err}")

                    # Try canvas / blob extraction in browser context for full resolution
                    if not saved:
                        b64_data = page.evaluate("""(element) => {
                            try {
                                const canvas = document.createElement('canvas');
                                canvas.width = element.naturalWidth || element.clientWidth || 1024;
                                canvas.height = element.naturalHeight || element.clientHeight || 1024;
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(element, 0, 0, canvas.width, canvas.height);
                                return canvas.toDataURL('image/png').split(',')[1];
                            } catch (e) {
                                return null;
                            }
                        }""", img)

                        if b64_data:
                            import base64
                            with open(img_path, "wb") as f:
                                f.write(base64.b64decode(b64_data))
                            saved = True
                            print(f"📸 Extracted full-res canvas image #{img_idx}")

                    if saved:
                        generated_files.append(img_filename)
                        img_idx += 1
            except Exception as e:
                print(f"⚠️ Error saving image #{img_idx}: {e}")

        # Check for generated videos (video element or downloadable video links / blob)
        videos = page.query_selector_all('model-response video, div[data-test-id="conversation-turn"] video, source[type*="video"], a[href*=".mp4"]')
        vid_idx = 1
        for vid in videos:
            try:
                src = vid.get_attribute("src") or vid.get_attribute("href")
                if src:
                    vid_filename = f"generated_video_{vid_idx}.mp4"
                    vid_path = os.path.join(args.output_dir, vid_filename)
                    if src.startswith("http"):
                        download_file(src, vid_path)
                        generated_files.append(vid_filename)
                        print(f"🎥 Downloaded generated video #{vid_idx}")
                        vid_idx += 1
                    elif src.startswith("blob:"):
                        b64_vid = page.evaluate("""async (url) => {
                            try {
                                const response = await fetch(url);
                                const blob = await response.blob();
                                return new Promise((resolve) => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                    reader.readAsDataURL(blob);
                                });
                            } catch (e) {
                                return null;
                            }
                        }""", src)
                        if b64_vid:
                            import base64
                            with open(vid_path, "wb") as f:
                                f.write(base64.b64decode(b64_vid))
                            generated_files.append(vid_filename)
                            print(f"🎥 Extracted video blob #{vid_idx}")
                            vid_idx += 1
            except Exception as e:
                print(f"⚠️ Error downloading video #{vid_idx}: {e}")

        browser.close()

    # Encode primary generated media file to base64 for n8n payload
    primary_media_b64 = None
    primary_media_type = None
    primary_media_name = None

    media_candidates = [f for f in generated_files if f != "response_screenshot.png"]
    if media_candidates:
        target_file = media_candidates[0]
        target_path = os.path.join(args.output_dir, target_file)
        if os.path.exists(target_path):
            import base64
            with open(target_path, "rb") as mf:
                primary_media_b64 = base64.b64encode(mf.read()).decode("utf-8")
            primary_media_name = target_file
            if target_file.endswith(".mp4"):
                primary_media_type = "video/mp4"
            elif target_file.endswith(".png"):
                primary_media_type = "image/png"
            elif target_file.endswith(".jpg") or target_file.endswith(".jpeg"):
                primary_media_type = "image/jpeg"

    # Save output metadata
    result_data = {
        "status": "success",
        "prompt": args.prompt,
        "image_url": args.image_url,
        "response_text": text_response,
        "generated_files": generated_files,
        "primary_media_name": primary_media_name,
        "primary_media_b64": primary_media_b64,
        "primary_media_type": primary_media_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(result_metadata_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Scraping completed. Output metadata saved to '{result_metadata_path}'.")

if __name__ == "__main__":
    main()
