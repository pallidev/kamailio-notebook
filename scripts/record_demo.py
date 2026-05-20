"""Record Jupyter Lab demo video using Playwright."""
import asyncio
import os
from playwright.async_api import async_playwright

JUPYTER_URL = "http://127.0.0.1:8888"
VIDEO_DIR = "/tmp/kam_demo_frames"
os.makedirs(VIDEO_DIR, exist_ok=True)

NOTEBOOKS = [
    "notebooks/curriculum/en/01-beginner/01-hello-kamailio.ipynb",
    "notebooks/curriculum/en/01-beginner/02-variables-and-types.ipynb",
    "notebooks/curriculum/en/01-beginner/03-routing-basics.ipynb",
    "notebooks/curriculum/en/02-intermediate/01-transformations.ipynb",
    "notebooks/curriculum/en/02-intermediate/02-dispatcher-and-routing.ipynb",
    "notebooks/curriculum/en/03-advanced/01-dialog-and-failover.ipynb",
]


async def screenshot(page, frame_num):
    path = f"{VIDEO_DIR}/frame_{frame_num:05d}.png"
    await page.screenshot(path=path, full_page=False)
    return frame_num + 1


async def dismiss_dialogs(page):
    for _ in range(10):
        try:
            dialog = page.locator(".jp-Dialog")
            if await dialog.is_visible(timeout=500):
                ok = dialog.locator("button.jp-mod-accept, button:has-text('Ok'), button:has-text('OK')")
                if await ok.first.is_visible(timeout=300):
                    await ok.first.click()
                    await page.wait_for_timeout(500)
        except:
            break


async def main():
    frame_num = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        # Open launcher
        await page.goto(JUPYTER_URL + "/lab", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await dismiss_dialogs(page)
        frame_num = await screenshot(page, frame_num)

        for nb_idx, nb_path in enumerate(NOTEBOOKS):
            nb_name = os.path.basename(nb_path).replace(".ipynb", "")
            print(f"\n=== {nb_idx+1}. {nb_name} ===")

            # Open notebook via URL
            url = f"{JUPYTER_URL}/lab/tree/{nb_path}"
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(3000)
            await dismiss_dialogs(page)
            await page.wait_for_timeout(1000)

            # Get the active (non-hidden) notebook panel
            active_panel = page.locator(".jp-NotebookPanel:not(.lm-mod-hidden)")
            try:
                if not await active_panel.is_visible(timeout=3000):
                    print(f"  Skipping {nb_name} - not visible")
                    continue
            except:
                print(f"  Skipping {nb_name} - no panel")
                continue

            # Select kernel via toolbar if needed
            try:
                kernel_btn = page.locator(".jp-KernelSelector button, .jp-ToolbarButtonComponent[title*='Kernel']")
            except:
                pass

            # Find cells in the active panel
            cells = active_panel.locator(".jp-Notebook .jp-Cell")
            cell_count = await cells.count()
            print(f"  {cell_count} cells")

            # Click first cell to focus
            await cells.first.click()
            await page.wait_for_timeout(300)
            frame_num = await screenshot(page, frame_num)

            # Execute cells one by one with Shift+Enter
            for cell_idx in range(cell_count):
                await page.keyboard.press("Shift+Enter")
                await page.wait_for_timeout(2000)
                frame_num = await screenshot(page, frame_num)
                # Smooth frames
                for _ in range(2):
                    await page.wait_for_timeout(300)
                    frame_num = await screenshot(page, frame_num)

            print(f"  {nb_name} complete")

            # Pause at end
            for _ in range(4):
                await page.wait_for_timeout(400)
                frame_num = await screenshot(page, frame_num)

            # Close this notebook tab (via Command Palette)
            await page.keyboard.press("Control+W")
            await page.wait_for_timeout(1000)

        print(f"\nTotal frames: {frame_num}")
        await browser.close()

    # Encode video
    print("Encoding video...")
    os.system(
        f"ffmpeg -y -framerate 5 -i {VIDEO_DIR}/frame_%05d.png "
        f"-c:v libx264 -pix_fmt yuv420p -preset fast -crf 18 "
        f"-vf 'scale=1920:1080' -movflags +faststart "
        f"docs/images/demo-jupyter-lab.mp4 2>/dev/null"
    )

    if os.path.exists("docs/images/demo-jupyter-lab.mp4"):
        size_mb = os.path.getsize("docs/images/demo-jupyter-lab.mp4") / 1024 / 1024
        print(f"Saved: docs/images/demo-jupyter-lab.mp4 ({size_mb:.1f} MB)")
    else:
        print("Encoding failed")

    os.system(f"rm -rf {VIDEO_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
