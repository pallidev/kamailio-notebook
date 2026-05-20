"""Record ~15s Jupyter Lab demo: notebooks + AI chat + help. Headed browser with video recording."""
import asyncio, os
from playwright.async_api import async_playwright

JUPYTER_URL = "http://127.0.0.1:8888"
VIDEO_DIR = "/tmp/kam_video"
os.makedirs(VIDEO_DIR, exist_ok=True)

NOTEBOOKS = [
    ("notebooks/curriculum/en/01-beginner/01-hello-kamailio.ipynb", "Hello"),
    ("notebooks/curriculum/en/02-intermediate/01-transformations.ipynb", "Transforms"),
    ("notebooks/curriculum/en/02-intermediate/02-dispatcher-and-routing.ipynb", "Dispatcher"),
]


async def dismiss(page):
    for _ in range(5):
        try:
            d = page.locator(".jp-Dialog")
            if await d.is_visible(timeout=300):
                ok = d.locator("button.jp-mod-accept")
                if await ok.first.is_visible(timeout=200):
                    await ok.first.click()
                    await page.wait_for_timeout(300)
        except:
            break


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=VIDEO_DIR,
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await ctx.new_page()

        # 1. Launcher
        await page.goto(f"{JUPYTER_URL}/lab", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        print("1. Launcher")

        # 2. Run notebooks
        for nb_path, nb_name in NOTEBOOKS:
            print(f"2. {nb_name}")
            await page.goto(f"{JUPYTER_URL}/lab/tree/{nb_path}", wait_until="networkidle")
            await page.wait_for_timeout(4000)
            await dismiss(page)
            await page.wait_for_timeout(1000)

            panel = page.locator(".jp-NotebookPanel:not(.lm-mod-hidden)")
            try:
                if not await panel.is_visible(timeout=3000):
                    continue
            except:
                continue

            cells = panel.locator(".jp-Notebook .jp-Cell")
            total = await cells.count()
            await cells.first.click()
            await page.wait_for_timeout(200)

            for ci in range(total):
                await page.keyboard.press("Shift+Enter")
                await page.wait_for_timeout(800)

            print(f"   {total} cells executed")
            await page.keyboard.press("Control+W")
            await page.wait_for_timeout(500)

        # 3. AI Chat - open chat panel
        print("3. AI Chat")
        try:
            chat_tab = page.locator(".lm-TabBar-tab[title*='Jupyter Chat']")
            if await chat_tab.is_visible(timeout=2000):
                await chat_tab.click()
                await page.wait_for_timeout(2000)

                # Look for chat input
                found = False
                for sel in ["textarea", "[contenteditable='true']", "input[type='text']"]:
                    els = page.locator(sel)
                    count = await els.count()
                    for i in range(count):
                        el = els.nth(i)
                        if await el.is_visible():
                            await el.click()
                            await page.wait_for_timeout(200)
                            await page.keyboard.type("@claude What does $ru mean in Kamailio?", delay=30)
                            await page.wait_for_timeout(500)
                            await page.keyboard.press("Enter")
                            print("   Chat message sent")

                            # Wait for response (fast-forward)
                            await page.wait_for_timeout(15000)
                            found = True
                            break
                    if found:
                        break

                if not found:
                    print("   No chat input, trying new chat button")
                    new_chat = page.locator("button:has-text('New'), button:has-text('+')")
                    if await new_chat.first.is_visible(timeout=1000):
                        await new_chat.first.click()
                        await page.wait_for_timeout(2000)
                        print("   New chat opened")
            else:
                print("   Chat tab not found")
        except Exception as e:
            print(f"   Chat error: {e}")

        # 4. Help command
        print("4. Help")
        try:
            await page.goto(f"{JUPYTER_URL}/lab", wait_until="networkidle")
            await page.wait_for_timeout(2000)
            nb_card = page.locator(".jp-LauncherCard").first
            if await nb_card.is_visible(timeout=2000):
                await nb_card.click()
                await page.wait_for_timeout(2000)
                kam = page.locator("text=Kamailio CFG")
                if await kam.is_visible(timeout=1000):
                    await kam.click()
                    await page.wait_for_timeout(300)
                    sel = page.locator("button:has-text('Select')")
                    if await sel.is_visible(timeout=300):
                        await sel.click()
                        await page.wait_for_timeout(2000)
                editor = page.locator(".jp-Cell .cm-content, .jp-Cell .CodeMirror")
                if await editor.first.is_visible(timeout=2000):
                    await editor.first.click()
                    await page.keyboard.type("%%help ds_select_dst", delay=35)
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Shift+Enter")
                    await page.wait_for_timeout(3000)
                    print("   Help executed")
        except Exception as e:
            print(f"   Help error: {e}")

        # Close and save video
        video_path = await page.video.path()
        print(f"\nRaw video: {video_path}")
        await ctx.close()
        await browser.close()

    # Convert to mp4 and gif
    print("Encoding...")
    os.system(
        f"ffmpeg -y -i {video_path} "
        f"-c:v libx264 -pix_fmt yuv420p -preset fast -crf 18 "
        f"-vf 'scale=1920:1080' -movflags +faststart "
        f"docs/images/demo-jupyter-lab.mp4 2>/dev/null"
    )
    os.system(
        f"ffmpeg -y -i {video_path} "
        f"-vf 'scale=960:-1:flags=lanczos,fps=10' "
        f"docs/images/demo-jupyter-lab.gif 2>/dev/null"
    )

    for ext in ["mp4", "gif"]:
        f = f"docs/images/demo-jupyter-lab.{ext}"
        if os.path.exists(f):
            print(f"  {f}: {os.path.getsize(f)/1024/1024:.1f} MB")

    os.system(f"rm -rf {VIDEO_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
