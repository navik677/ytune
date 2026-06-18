"""ytune entry point — CLI and main() function."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys


def check_dependencies() -> list[str]:
    """Check that required system dependencies are available."""
    missing = []

    # Check mpv
    if not shutil.which("mpv"):
        missing.append("mpv (install with: sudo apt install mpv)")

    # Check yt-dlp
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp (install with: pip install yt-dlp)")

    return missing


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.FileHandler("/tmp/ytune.log"), logging.StreamHandler()],
    )


def run_chromium_auth() -> None:
    """Run browser login using Playwright Chromium."""
    import time
    from playwright.sync_api import sync_playwright
    from ytune.config import get_config_dir
    import json
    
    oauth_path = get_config_dir() / "oauth.json"
    
    print("\nStarting Chromium browser...")
    print("Please log in to your YouTube Music account in the browser window.")
    print("The application will automatically detect your login, save it, and close the browser.")
    print("Waiting for login...")
    print()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://music.youtube.com")
            
            logged_in = False
            cookies = []
            user_agent = page.evaluate("navigator.userAgent")
            
            while not logged_in:
                time.sleep(1)
                
                # Check if browser was closed
                if browser.contexts == []:
                    print("Browser closed before authentication completed.")
                    return
                    
                cookies = context.cookies('https://music.youtube.com')
                # Accept both standard 3P and 1P cookies since browser privacy settings might block 3P cookies.
                sapisid_cookie = next((c for c in cookies if c["name"] in ("__Secure-3PAPISID", "__Secure-1PAPISID")), None)
                psidts_cookie = next((c for c in cookies if c["name"] in ("__Secure-3PSIDTS", "__Secure-1PSIDTS")), None)
                is_on_ytdomain = "music.youtube.com" in page.url
                
                if sapisid_cookie and psidts_cookie and is_on_ytdomain:
                    print("✓ Session tokens detected! Completing setup in 3 seconds...")
                    time.sleep(3)
                    cookies = context.cookies('https://music.youtube.com')
                    logged_in = True
                    break
            
            print("✓ Login detected! Extracting session...")
            
            cookie_parts = []
            for c in cookies:
                cookie_parts.append(f"{c['name']}={c['value']}")
            cookie_str = "; ".join(cookie_parts)
            
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/json",
                "cookie": cookie_str,
                "origin": "https://music.youtube.com",
                "user-agent": user_agent,
                "x-goog-authuser": "0",
                "Authorization": "SAPISIDHASH dummy"
            }
            
            with open(oauth_path, "w") as f:
                json.dump(headers, f, indent=4)
                
            print(f"✓ Authentication successful!")
            print(f"  Credentials saved to: {oauth_path}")
            browser.close()
            
            # Verify browser headers
            print("Verifying authentication credentials...")
            try:
                from ytmusicapi import YTMusic
                yt = YTMusic(str(oauth_path))
                if yt.auth_type.name == "UNAUTHORIZED":
                    print("✗ Verification failed: Client is unauthenticated.")
                else:
                    print(f"✓ Verification successful! Auth type: {yt.auth_type.name}")
                    # Try a call that is only available when signed in
                    yt.get_liked_songs(limit=1)
                    print("✓ Successfully connected to your Library!")
            except Exception as e:
                print(f"✗ Verification warning: {e}")
                
    except Exception as e:
        print(f"✗ Failed to run Chromium auth: {e}")
        print("Please fallback to Option 2 (Manual Browser Headers).")


def cmd_auth() -> None:
    """Run authentication setup."""
    print("╔══════════════════════════════════════════╗")
    print("║  ytune — YouTube Music Authentication    ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print("Select authentication method:")
    print("  1. Browser Auto Login (Recommended — opens Chromium to sign in, captures cookies automatically)")
    print("  2. Manual Browser Headers (For headless servers or if Chromium launch fails)")
    print("  3. OAuth (Requires your own Google Cloud Console Client ID & Secret)")
    print()
    choice = input("Enter choice [1/2/3, default: 1]: ").strip()
    if not choice:
        choice = "1"

    try:
        from ytune.ytmusic_client import YTMusicClient
        if choice == "1":
            # Check DISPLAY to warn if headless
            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                print("\n⚠️  No graphical DISPLAY detected! headed Chromium auto login might fail.")
                print("Defaulting to Option 2 (Manual Browser Headers) is recommended.")
                cont = input("Attempt Chromium launch anyway? [y/N]: ").strip().lower()
                if cont != 'y':
                    choice = "2"
            
            if choice == "1":
                run_chromium_auth()
                print(f"\n  You can now run 'ytune' to start the player.")
                return

        if choice == "2":
            print("\nTo authenticate using browser headers:")
            print("1. Open your browser and log in to https://music.youtube.com")
            print("2. Open Developer Tools (F12) -> Network tab")
            print("3. Refresh the page or click 'Library'. Find a POST request to 'browse'.")
            print("4. Right-click that request -> Copy -> Copy request headers")
            print("5. Paste the copied headers below and press Enter twice (or Ctrl+D to finish):")
            print()
            
            lines = []
            while True:
                try:
                    line = input()
                    if not line and lines and not lines[-1]:
                        break
                    lines.append(line)
                except EOFError:
                    break
            
            headers_raw = "\n".join(lines).strip()
            if not headers_raw:
                print("\nNo headers provided. Authentication cancelled.")
                return
                
            path = YTMusicClient.setup_browser(headers_raw)
            print(f"\n✓ Authentication file saved to: {path}")
            
            # Verify browser headers
            print("Verifying authentication credentials...")
            try:
                from ytmusicapi import YTMusic
                yt = YTMusic(path)
                if yt.auth_type.name == "UNAUTHORIZED":
                    print("✗ Verification failed: Client is unauthenticated.")
                else:
                    print(f"✓ Verification successful! Auth type: {yt.auth_type.name}")
                    # Try a call that is only available when signed in
                    yt.get_liked_songs(limit=1)
                    print(f"✓ Successfully fetched library data and verified account connection.")
            except Exception as e:
                print(f"✗ Verification failed: {e}")
                print("  Please make sure you copied headers from a request where you are signed in (should contain Cookie with __Secure-3PAPISID).")
            
        elif choice == "3":
            print("\nOAuth Setup:")
            print("1. Go to https://console.cloud.google.com and create a project.")
            print("2. Enable the YouTube Data API v3.")
            print("3. Go to Credentials -> Create Credentials -> OAuth client ID.")
            print("4. Select Application Type: 'TVs and Limited Input devices'.")
            print("5. Enter the client details below:")
            client_id = input("Client ID: ").strip()
            client_secret = input("Client Secret: ").strip()
            
            if not client_id or not client_secret:
                print("\nClient ID and Secret are required. Authentication cancelled.")
                return
                
            path = YTMusicClient.setup_oauth(client_id, client_secret)
            print(f"\n✓ OAuth Authentication successful!")
            print(f"  Credentials saved to: {path}")
            
            # Verify OAuth
            print("Verifying OAuth credentials...")
            try:
                from ytmusicapi import YTMusic
                yt = YTMusic(path)
                if yt.auth_type.name == "UNAUTHORIZED":
                    print("✗ Verification failed: Client is unauthenticated.")
                else:
                    print(f"✓ Verification successful! Auth type: {yt.auth_type.name}")
                    # Try a call that is only available when signed in
                    yt.get_liked_songs(limit=1)
                    print("✓ Successfully fetched library data and verified account connection!")
            except Exception as e:
                print(f"✗ Verification failed: {e}")
            
        else:
            print("\nInvalid choice. Authentication cancelled.")
            sys.exit(1)
            
        print(f"\n  You can now run 'ytune' to start the player.")
        
    except KeyboardInterrupt:
        print("\n\nAuthentication cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
        sys.exit(1)


def cmd_play() -> None:
    """Launch the TUI player."""
    # Check dependencies
    missing = check_dependencies()
    if missing:
        print("Missing required dependencies:")
        for dep in missing:
            print(f"  ✗ {dep}")
        print()
        print("Install them and try again.")
        sys.exit(1)

    # Launch the app
    from ytune.app import YTuneApp
    app = YTuneApp()
    app.run()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ytune",
        description="ytune — Terminal YouTube Music Player",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ytune              Launch the player
  ytune auth         Set up YouTube Music authentication
  ytune --verbose    Launch with debug logging

Keyboard shortcuts (in player):
  space    Play/Pause          /    Search
  n        Next track           a    Add to queue
  p        Previous track       d    Remove from queue
  r        Cycle repeat         z    Toggle shuffle
  +/-      Volume up/down       q    Quit
  ←/→      Seek ±5 seconds
        """,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="play",
        choices=["play", "auth"],
        help="Command to run (default: play)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "auth":
        cmd_auth()
    else:
        cmd_play()


if __name__ == "__main__":
    main()
