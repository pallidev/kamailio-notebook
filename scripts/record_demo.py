"""Record ~15s Jupyter Lab demo: notebooks + AI chat + help. WebP for README."""
import asyncio, os
from playwright.async_api import async_playwright

JUPYTER_URL = "http://127.0.0.1:8888"
V = "/tmp/kam_demo_frames"
os.makedirs(V, exist_ok=True)
FPS = 10

async def ss(page, fn):
    await page.screenshot(path=f"{V}/frame_{fn:05d}.png", full_page=False)
    return fn + 1

async def burst(page, fn, n, ms=150):
    for _ in range(n):
        await page.wait_for_timeout(ms)
        fn = await ss(page, fn)
    return fn

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

async def run_notebook(page, fn, url, name, show_every=2):
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(4000)
    await dismiss(page)
    await page.wait_for_timeout(1000)
    panel = page.locator(".jp-NotebookPanel:not(.lm-mod-hidden)")
    try:
        if not await panel.is_visible(timeout=3000):
            return fn
    except:
        return fn
    cells = panel.locator(".jp-Notebook .jp-Cell")
    total = await cells.count()
    await cells.first.click()
    await page.wait_for_timeout(200)
    fn = await ss(page, fn)
    for ci in range(total):
        await page.keyboard.press("Shift+Enter")
        await page.wait_for_timeout(700)
        if ci % show_every == 0:
            fn = await ss(page, fn)
    fn = await burst(page, fn, 3, 200)
    print(f"  {name}: {total} cells")
    return fn


async def main():
    fn = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()

        # 1. Launcher (~1s)
        await page.goto(f"{JUPYTER_URL}/lab", wait_until="networkidle")
        await page.wait_for_timeout(4000)
        fn = await burst(page, fn, 10, 100)
        print("1. Launcher")

        # 2. Hello Kamailio (~3s)
        fn = await run_notebook(page, fn,
            f"{JUPYTER_URL}/lab/tree/notebooks/curriculum/en/01-beginner/01-hello-kamailio.ipynb",
            "Hello", show_every=2)

        # 3. Transformations (~2s)
        await page.keyboard.press("Control+W")
        await page.wait_for_timeout(500)
        fn = await run_notebook(page, fn,
            f"{JUPYTER_URL}/lab/tree/notebooks/curriculum/en/02-intermediate/01-transformations.ipynb",
            "Transforms", show_every=3)

        # 4. Dispatcher (~2s)
        await page.keyboard.press("Control+W")
        await page.wait_for_timeout(500)
        fn = await run_notebook(page, fn,
            f"{JUPYTER_URL}/lab/tree/notebooks/curriculum/en/02-intermediate/02-dispatcher-and-routing.ipynb",
            "Dispatcher", show_every=3)

        # 5. AI Chat with @claude (~5s including fast-forward)
        print("5. AI Chat")
        try:
            # Click the Jupyter Chat tab in the right sidebar
            chat_tab = page.locator(".lm-TabBar-tab[title*='Jupyter Chat']")
            if await chat_tab.is_visible(timeout=2000):
                await chat_tab.click()
                await page.wait_for_timeout(2000)
                fn = await burst(page, fn, 5, 150)  # show chat panel

                # Find chat textarea (appears after panel is visible)
                chat_input = None
                for sel in [
                    "textarea[placeholder*='message' i]",
                    "textarea[placeholder*='chat' i]",
                    ".jp-chat-input textarea",
                    "textarea",
                ]:
                    loc = page.locator(sel)
                    if await loc.count() > 0:
                        # Use the last visible textarea (chat input is usually last)
                        for i in range(await loc.count()):
                            if await loc.nth(i).is_visible(timeout=500):
                                chat_input = loc.nth(i)
                        if chat_input:
                            break

                if chat_input and await chat_input.is_visible(timeout=1000):
                    await chat_input.click()
                    await page.wait_for_timeout(200)

                    # Type @claude question
                    await page.keyboard.type("@claude What does $ru mean in Kamailio cfg?", delay=30)
                    fn = await burst(page, fn, 8, 100)  # show typing
                    await page.keyboard.press("Enter")

                    # Fast-forward: 1 frame per second for response
                    for i in range(40):
                        await page.wait_for_timeout(1000)
                        fn = await ss(page, fn)
                        # After getting enough response frames, stop
                        if i > 10:
                            # Check if response seems complete
                            msgs = page.locator("[data-testid='chat-message'], .jp-chat-message, .chat-message")
                            if await msgs.count() > 1 and i > 15:
                                fn = await burst(page, fn, 3, 200)
                                break

                    print(f"  Chat done (fn={fn})")
                else:
                    print("  No chat input found")
                    fn = await burst(page, fn, 5, 200)
            else:
                print("  No Jupyter Chat tab")
                fn = await burst(page, fn, 5, 200)
        except Exception as e:
            print(f"  Chat error: {e}")
            fn = await burst(page, fn, 5, 200)

        # 6. %%help (~2s)
        print("6. Help")
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
                    fn = await burst(page, fn, 8, 100)
                    await page.keyboard.press("Shift+Enter")
                    await page.wait_for_timeout(2000)
                    fn = await burst(page, fn, 8, 200)
        except Exception as e:
            print(f"  Help error: {e}")

        await browser.close()

    dur = fn / FPS
    print(f"\nTotal: {fn} frames, {dur:.1f}s @ {FPS}fps")

    os.system(
        f"ffmpeg -y -framerate {FPS} -i {V}/frame_%05d.png "
        f"-c:v libx264 -pix_fmt yuv420p -preset fast -crf 18 "
        f"-vf 'scale=1920:1080' -movflags +faststart "
        f"docs/images/demo-jupyter-lab.mp4 2>/dev/null"
    )
    os.system(
        f"ffmpeg -y -framerate {FPS} -i {V}/frame_%05d.png "
        f"-vf 'scale=960:-1:flags=lanczos,fps={FPS}' "
        f"-vcodec libwebp -lossless 0 -compression_level 6 "
        f"-q:v 65 -loop 0 -preset default "
        f"docs/images/demo-jupyter-lab.webp 2>/dev/null"
    )
    for ext in ["mp4", "webp"]:
        f = f"docs/images/demo-jupyter-lab.{ext}"
        if os.path.exists(f):
            print(f"  {f}: {os.path.getsize(f)/1024/1024:.1f} MB")
    os.system(f"rm -rf {V}")


if __name__ == "__main__":
    asyncio.run(main())
