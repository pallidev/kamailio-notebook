"""Generate a 15-second terminal demo video for YouTube Shorts."""

import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

# Settings
WIDTH = 1080
HEIGHT = 1920
BG_COLOR = (30, 30, 30)
PROMPT_COLOR = (0, 255, 65)
CODE_COLOR = (255, 255, 255)
OUTPUT_COLOR = (100, 200, 255)
ACCENT_COLOR = (255, 70, 70)
DIM_COLOR = (120, 120, 120)
FPS = 15
DURATION = 15
TOTAL_FRAMES = FPS * DURATION
FRAME_DIR = "/tmp/kam_frames"
os.makedirs(FRAME_DIR, exist_ok=True)

# Try to find a good font
font_paths = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/Library/Fonts/FiraCode-Regular.ttf",
    "/System/Library/Fonts/SFCompact.ttf",
]
font_path = None
for p in font_paths:
    if os.path.exists(p):
        font_path = p
        break

def get_font(size):
    try:
        return ImageFont.truetype(font_path or "/System/Library/Fonts/Menlo.ttc", size)
    except:
        return ImageFont.load_default()

# Scene definitions: (text_lines, duration_seconds, style)
# Each line is (text, color, font_size)
scenes = [
    # Scene 1: Hook (2s)
    {
        "duration": 2.0,
        "lines": [
            ("", None, 20),
            ("", None, 20),
            ("", None, 20),
            ("", None, 20),
            ("Kamailio cfg", ACCENT_COLOR, 48),
            ("learning sucks.", ACCENT_COLOR, 48),
            ("", None, 20),
            ("What if you could", (200, 200, 200), 32),
            ("TEST it like THIS?", PROMPT_COLOR, 40),
        ],
    },
    # Scene 2: Install (1.5s)
    {
        "duration": 1.5,
        "lines": [
            ("", None, 20),
            ("$ pip install kamailio-notebook", PROMPT_COLOR, 32),
            ("", None, 20),
            ("  ✓ Installing... done", OUTPUT_COLOR, 28),
            ("  ✓ Kernel registered", OUTPUT_COLOR, 28),
            ("", None, 20),
            ("$ jupyter lab", PROMPT_COLOR, 32),
        ],
    },
    # Scene 3: SIP Mock (2.5s)
    {
        "duration": 2.5,
        "lines": [
            ("", None, 16),
            ("── Cell [1] ──────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  %%sip INVITE", PROMPT_COLOR, 32),
            ("  From: <sip:1001@corp.com>", CODE_COLOR, 26),
            ("  To: <sip:1002@corp.com>", CODE_COLOR, 26),
            ("", None, 12),
            ("── Output ────────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  ✓ Mock INVITE created", OUTPUT_COLOR, 28),
            ("  $rm = INVITE", PROMPT_COLOR, 30),
            ("  $fu = sip:1001@corp.com", PROMPT_COLOR, 30),
            ("  $ru = sip:1002@corp.com", PROMPT_COLOR, 30),
        ],
    },
    # Scene 4: Transformation (2s)
    {
        "duration": 2.0,
        "lines": [
            ("", None, 16),
            ("── Cell [2] ──────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  $(ru{uri.user})", PROMPT_COLOR, 36),
            ("", None, 12),
            ("── Output ────────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ('  "1002"', OUTPUT_COLOR, 48),
            ("", None, 20),
            ("  ← Just the user part!", DIM_COLOR, 24),
        ],
    },
    # Scene 5: If/Else Routing (3s)
    {
        "duration": 3.0,
        "lines": [
            ("", None, 16),
            ("── Cell [3] ──────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  if (is_method(\"INVITE\")) {", PROMPT_COLOR, 28),
            ("      record_route();", PROMPT_COLOR, 28),
            ("      t_relay();", PROMPT_COLOR, 28),
            ("  }", PROMPT_COLOR, 28),
            ("", None, 12),
            ("── Output ────────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  ✓ if (is_method(\"INVITE\"))", PROMPT_COLOR, 30),
            ("       → TRUE", PROMPT_COLOR, 30),
            ("  → record_route()", OUTPUT_COLOR, 28),
            ("  → t_relay()", OUTPUT_COLOR, 28),
        ],
    },
    # Scene 6: Diff (2s)
    {
        "duration": 2.0,
        "lines": [
            ("", None, 16),
            ("── Cell [4] ──────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  %%diff", PROMPT_COLOR, 36),
            ("", None, 12),
            ("── Output ────────────────────", DIM_COLOR, 22),
            ("", None, 12),
            ("  ~ $ru: example.com", (255, 200, 50), 28),
            ("       → 10.60.91.199:5060", PROMPT_COLOR, 28),
            ("  + $var(caller): \"1001\"", (100, 255, 100), 28),
            ("  + $var(port): 5060", (100, 255, 100), 28),
        ],
    },
    # Scene 7: CTA (2s)
    {
        "duration": 2.0,
        "lines": [
            ("", None, 20),
            ("", None, 20),
            ("", None, 20),
            ("", None, 20),
            ("", None, 20),
            ("kamailio-notebook", ACCENT_COLOR, 44),
            ("", None, 20),
            ("Interactive Jupyter Kernel", (200, 200, 200), 28),
            ("for Kamailio cfg scripting", (200, 200, 200), 28),
            ("", None, 30),
            ("github.com/pallidev/", PROMPT_COLOR, 24),
            ("  kamailio-notebook", PROMPT_COLOR, 24),
            ("", None, 20),
            ("MIT License · Open Source", DIM_COLOR, 22),
        ],
    },
]


def render_frame(lines, progress=1.0):
    """Render a single frame."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = 120  # top margin

    # Render title bar
    draw.rectangle([(0, 0), (WIDTH, 70)], fill=(45, 45, 45))
    title_font = get_font(24)
    draw.text((40, 22), "kamailio-notebook", fill=OUTPUT_COLOR, font=title_font)

    # Render dots (traffic light)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([(WIDTH - 120 + i * 35, 25), (WIDTH - 95 + i * 35, 50)], fill=color)

    y = 140

    # Count visible lines based on progress
    total_chars = sum(len(text) for text, _, _ in lines if text)
    visible_chars = int(total_chars * progress)

    char_count = 0
    for text, color, font_size in lines:
        if not text:
            y += font_size
            continue

        font = get_font(font_size)
        # Calculate how much of this line to show
        line_chars = len(text)
        if char_count + line_chars <= visible_chars:
            # Show full line
            draw.text((60, y), text, fill=color or CODE_COLOR, font=font)
            char_count += line_chars
        elif char_count < visible_chars:
            # Partial line
            partial = text[:visible_chars - char_count]
            draw.text((60, y), partial, fill=color or CODE_COLOR, font=font)
            # Draw cursor
            cursor_x = 60 + font.getlength(partial)
            draw.rectangle([(cursor_x, y), (cursor_x + 2, y + font_size)], fill=PROMPT_COLOR)
            char_count = visible_chars
            break
        else:
            break

        y += font_size + 8

    return img


def main():
    print(f"Generating {TOTAL_FRAMES} frames for {DURATION}s video...")

    frame_num = 0
    for scene_idx, scene in enumerate(scenes):
        scene_frames = int(scene["duration"] * FPS)
        lines = scene["lines"]

        for i in range(scene_frames):
            # Progress within this scene (0 to 1)
            # First 70% is typing, last 30% is pause
            if i < scene_frames * 0.7:
                progress = (i / (scene_frames * 0.7))
            else:
                progress = 1.0

            img = render_frame(lines, progress)

            # Add subtle scan line effect for cinematic feel
            draw = ImageDraw.Draw(img)
            for sy in range(0, HEIGHT, 4):
                if (sy + frame_num) % 8 == 0:
                    draw.line([(0, sy), (WIDTH, sy)], fill=(0, 0, 0), width=1)

            img.save(f"{FRAME_DIR}/frame_{frame_num:04d}.png")
            frame_num += 1

        print(f"  Scene {scene_idx + 1}/{len(scenes)} done ({scene_frames} frames)")

    print(f"\nTotal frames: {frame_num}")
    print(f"Encoding to MP4...")

    # Encode with ffmpeg
    os.system(
        f"ffmpeg -y -framerate {FPS} -i {FRAME_DIR}/frame_%04d.png "
        f"-c:v libx264 -pix_fmt yuv420p -preset fast -crf 18 "
        f"-movflags +faststart "
        f"docs/images/demo-shorts.mp4 2>/dev/null"
    )

    if os.path.exists("docs/images/demo-shorts.mp4"):
        size_mb = os.path.getsize("docs/images/demo-shorts.mp4") / 1024 / 1024
        print(f"\n✅ Video saved: docs/images/demo-shorts.mp4 ({size_mb:.1f} MB)")
        print(f"   Duration: {DURATION}s, Resolution: {WIDTH}x{HEIGHT}, FPS: {FPS}")
    else:
        print("❌ Video encoding failed")

    # Also create a WebP for GitHub README (smaller than GIF)
    print(f"\nCreating animated WebP for README...")
    os.system(
        f"ffmpeg -y -framerate {FPS} -i {FRAME_DIR}/frame_%04d.png "
        f"-vf 'scale=540:-1:flags=lanczos,fps=10' "
        f"-vcodec libwebp -lossless 0 -compression_level 6 "
        f"-q:v 65 -loop 0 -preset default "
        f"docs/images/demo-shorts.webp 2>/dev/null"
    )

    if os.path.exists("docs/images/demo-shorts.webp"):
        size_mb = os.path.getsize("docs/images/demo-shorts.webp") / 1024 / 1024
        print(f"✅ WebP saved: docs/images/demo-shorts.webp ({size_mb:.1f} MB)")

    # Cleanup
    print("\nCleaning up frames...")
    os.system(f"rm -rf {FRAME_DIR}")


if __name__ == "__main__":
    main()
